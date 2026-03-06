import os
import glob
import structlog
from pathlib import Path

logger = structlog.get_logger()


def load_daml_examples(examples_dir: str | None = None) -> list[dict]:
    if examples_dir is None:
        examples_dir = os.path.join(os.path.dirname(__file__), "daml_examples")

    documents = []
    daml_files = glob.glob(os.path.join(examples_dir, "*.daml"))

    for file_path in daml_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            file_name = Path(file_path).stem
            contract_type = _infer_contract_type(file_name, content)

            chunks = _chunk_daml_file(content, file_name)
            for chunk in chunks:
                documents.append({
                    "content":       chunk["content"],
                    "source":        file_path,
                    "file_name":     file_name,
                    "contract_type": contract_type,
                    "chunk_type":    chunk["type"],
                    "metadata": {
                        "source":        file_path,
                        "file_name":     file_name,
                        "contract_type": contract_type,
                        "chunk_type":    chunk["type"],
                    }
                })

        except Exception as e:
            logger.error("Failed to load Daml example", file=file_path, error=str(e))

    logger.info("Loaded Daml examples", count=len(documents), files=len(daml_files))
    return documents


def _infer_contract_type(file_name: str, content: str) -> str:
    type_map = {
        "bond":             "bond_tokenization",
        "equity":           "equity_token",
        "asset_transfer":   "asset_transfer",
        "escrow":           "escrow",
        "trade_settlement": "trade_settlement",
        "option":           "option_contract",
        "cash_payment":     "cash_payment",
        "nft":              "nft_ownership",
    }
    for key, contract_type in type_map.items():
        if key in file_name.lower():
            return contract_type
    return "generic"


def _chunk_daml_file(content: str, file_name: str) -> list[dict]:
    chunks = []
    chunks.append({"type": "full_file", "content": content})

    lines = content.split("\n")
    current_template = []
    in_template = False
    template_name = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("template "):
            if current_template and template_name:
                chunks.append({
                    "type":    "template",
                    "content": "\n".join(current_template),
                })
            template_name = stripped.replace("template ", "").strip()
            current_template = [line]
            in_template = True
        elif in_template:
            current_template.append(line)

    if current_template and template_name:
        chunks.append({
            "type":    "template",
            "content": "\n".join(current_template),
        })

    return chunks
