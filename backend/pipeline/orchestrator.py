import structlog
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from pipeline.state import PipelineState
from agents.intent_agent import run_intent_agent
from agents.writer_agent import run_writer_agent, fetch_rag_context
from agents.compile_agent import run_compile_agent
from agents.fix_agent import run_fix_agent
from agents.deploy_agent import run_deploy_agent
from config import get_settings

logger = structlog.get_logger()


def intent_node(state: dict) -> dict:
    logger.info("Node: intent", job_id=state.get("job_id"))
    try:
        intent = run_intent_agent(state["user_input"])
        return {
            **state,
            "structured_intent": intent,
            "current_step":      "Generating Daml code...",
            "progress":          20,
        }
    except Exception as e:
        logger.error("Intent node failed", error=str(e))
        return {
            **state,
            "error_message":  str(e),
            "is_fatal_error": True,
            "current_step":   "Failed at intent analysis",
            "progress":       0,
        }


def rag_node(state: dict) -> dict:
    logger.info("Node: RAG retrieval", job_id=state.get("job_id"))
    try:
        context = fetch_rag_context(state["structured_intent"])
        return {
            **state,
            "rag_context":  context,
            "current_step": "Writing Daml code...",
            "progress":     35,
        }
    except Exception as e:
        logger.warning("RAG retrieval failed, continuing without context", error=str(e))
        return {
            **state,
            "rag_context":  [],
            "current_step": "Writing Daml code...",
            "progress":     35,
        }


def generate_node(state: dict) -> dict:
    logger.info("Node: generate", job_id=state.get("job_id"))
    try:
        code = run_writer_agent(
            structured_intent=state["structured_intent"],
            rag_context=state.get("rag_context", []),
        )
        return {
            **state,
            "generated_code": code,
            "current_step":   "Compiling contract...",
            "progress":       50,
        }
    except Exception as e:
        logger.error("Generate node failed", error=str(e))
        return {
            **state,
            "error_message":  str(e),
            "is_fatal_error": True,
            "current_step":   "Failed at code generation",
            "progress":       0,
        }


def compile_node(state: dict) -> dict:
    job_id = state.get("job_id", "unknown")
    attempt = state.get("attempt_number", 0) + 1
    logger.info("Node: compile", job_id=job_id, attempt=attempt)

    try:
        result = run_compile_agent(state["generated_code"], job_id)
        return {
            **state,
            "compile_result":  "success" if result["success"] else result.get("raw_error", ""),
            "compile_success": result["success"],
            "compile_errors":  result.get("errors", []),
            "dar_path":        result.get("dar_path", ""),
            "attempt_number":  attempt,
            "current_step":    "Deploying to Canton..." if result["success"] else f"Auto-fixing errors (attempt {attempt})...",
            "progress":        65 if result["success"] else 55,
        }
    except Exception as e:
        logger.error("Compile node failed", error=str(e))
        return {
            **state,
            "compile_success": False,
            "compile_errors":  [{"message": str(e), "error_type": "unknown", "fixable": True}],
            "attempt_number":  attempt,
            "current_step":    "Compilation error",
        }


def fix_node(state: dict) -> dict:
    attempt = state.get("attempt_number", 1)
    logger.info("Node: fix", job_id=state.get("job_id"), attempt=attempt)

    try:
        fixed_code = run_fix_agent(
            daml_code=state["generated_code"],
            compile_errors=state.get("compile_errors", []),
            attempt_number=attempt,
        )
        return {
            **state,
            "generated_code": fixed_code,
            "current_step":   f"Re-compiling after fix (attempt {attempt})...",
            "progress":       58,
        }
    except Exception as e:
        logger.error("Fix node failed", error=str(e))
        return {
            **state,
            "error_message":  str(e),
            "is_fatal_error": True,
            "current_step":   "Auto-fix failed",
        }


def deploy_node(state: dict) -> dict:
    logger.info("Node: deploy", job_id=state.get("job_id"))

    settings = get_settings()
    canton_url = state.get("canton_url") or settings.get_canton_url()
    canton_env = state.get("canton_environment", "sandbox")

    try:
        result = run_deploy_agent(
            dar_path=state.get("dar_path", ""),
            structured_intent=state.get("structured_intent", {}),
            canton_url=canton_url,
            canton_environment=canton_env,
        )

        if result["success"]:
            return {
                **state,
                "contract_id":   result["contract_id"],
                "package_id":    result["package_id"],
                "explorer_link": result["explorer_link"],
                "current_step":  "Deployment complete!",
                "progress":      100,
            }
        else:
            return {
                **state,
                "error_message":  result.get("error", "Deployment failed"),
                "is_fatal_error": True,
                "current_step":   "Deployment failed",
                "progress":       80,
            }
    except Exception as e:
        logger.error("Deploy node failed", error=str(e))
        return {
            **state,
            "error_message":  str(e),
            "is_fatal_error": True,
            "current_step":   "Deployment failed",
        }


def error_node(state: dict) -> dict:
    logger.error("Pipeline reached error node", job_id=state.get("job_id"), error=state.get("error_message"))
    return {
        **state,
        "current_step": "Failed — max retries exceeded",
        "progress":     0,
    }


def _route_after_compile(state: dict) -> Literal["deploy", "fix", "error"]:
    settings = get_settings()

    if state.get("is_fatal_error"):
        return "error"

    if state.get("compile_success"):
        return "deploy"

    attempt = state.get("attempt_number", 0)
    if attempt >= settings.max_fix_attempts:
        return "error"

    return "fix"


def _route_after_intent(state: dict) -> Literal["rag", "error"]:
    if state.get("is_fatal_error"):
        return "error"
    return "rag"


def _route_after_generate(state: dict) -> Literal["compile", "error"]:
    if state.get("is_fatal_error"):
        return "error"
    return "compile"


def build_pipeline() -> CompiledStateGraph:
    graph = StateGraph(dict)

    graph.add_node("intent",   intent_node)
    graph.add_node("rag",      rag_node)
    graph.add_node("generate", generate_node)
    graph.add_node("compile",  compile_node)
    graph.add_node("fix",      fix_node)
    graph.add_node("deploy",   deploy_node)
    graph.add_node("error",    error_node)

    graph.set_entry_point("intent")

    graph.add_conditional_edges("intent", _route_after_intent, {"rag": "rag", "error": "error"})
    graph.add_edge("rag", "generate")
    graph.add_conditional_edges("generate", _route_after_generate, {"compile": "compile", "error": "error"})
    graph.add_conditional_edges(
        "compile",
        _route_after_compile,
        {"deploy": "deploy", "fix": "fix", "error": "error"},
    )
    graph.add_edge("fix", "compile")
    graph.add_edge("deploy", END)
    graph.add_edge("error",  END)

    return graph.compile()


def run_pipeline(job_id: str, user_input: str, canton_environment: str = "sandbox", canton_url: str = "") -> dict:
    settings = get_settings()

    initial_state = {
        "job_id":             job_id,
        "user_input":         user_input,
        "structured_intent":  {},
        "rag_context":        [],
        "generated_code":     "",
        "compile_result":     "",
        "compile_success":    False,
        "compile_errors":     [],
        "attempt_number":     0,
        "dar_path":           "",
        "contract_id":        "",
        "package_id":         "",
        "explorer_link":      "",
        "error_message":      "",
        "is_fatal_error":     False,
        "current_step":       "Analyzing your contract description...",
        "progress":           10,
        "canton_environment": canton_environment,
        "canton_url":         canton_url or settings.get_canton_url(),
    }

    pipeline = build_pipeline()
    final_state = pipeline.invoke(initial_state)

    logger.info(
        "Pipeline completed",
        job_id=job_id,
        success=bool(final_state.get("contract_id")),
        attempts=final_state.get("attempt_number"),
    )

    return final_state
