# GINIE-DAML REBUILD - IMPLEMENTATION PLAN

## 1. TARGET ARCHITECTURE

### New LangGraph Pipeline
```
User Input → prompt_enhancer → intent_agent → rag_retrieval → template_planner 
→ builder_agent (ReAct + tools) → syntax_validator → compile_agent 
→ fix_agent (if errors) → scenario_generator → test_runner → deploy_agent → Result
```

**Node Functions**:
- **prompt_enhancer**: Expand vague input to detailed DAML spec
- **intent_agent**: Parse → structured JSON (parties, features, constraints)
- **rag_retrieval**: ChromaDB similarity search for DAML patterns
- **template_planner**: Design module structure, template signatures, dependencies
- **builder_agent**: ReAct agent with DAML tools (create_template, add_choice, etc.)
- **syntax_validator**: Pre-compile checks (Party types, Decimal, signatory)
- **compile_agent**: Run `dpm build`, structured error parsing
- **fix_agent**: Targeted fixes based on error classification
- **scenario_generator**: Generate test scenarios from templates
- **test_runner**: Execute `daml test`
- **deploy_agent**: Canton v2 API deployment + verification

**Retry Logic**:
- syntax_validator → builder_agent (max 3)
- compile_agent → fix_agent → compile_agent (max 5)
- test_runner → fix_agent (max 3)

---

## 2. BACKEND STRUCTURE

```
backend/
├── agents/
│   ├── prompt_enhancer.py       [NEW]
│   ├── intent_agent.py          [MODIFY]
│   ├── template_planner.py      [NEW]
│   ├── builder_agent.py         [NEW - ReAct with tools]
│   ├── syntax_validator.py      [NEW]
│   ├── compile_agent.py         [MODIFY - structured errors]
│   ├── fix_agent.py             [MODIFY - targeted fixes]
│   ├── scenario_generator.py    [NEW]
│   ├── test_runner.py           [NEW]
│   └── deploy_agent.py          [MODIFY - v2 APIs]
│
├── tools/
│   ├── daml_tools.py            [NEW - 10+ generation tools]
│   ├── compilation_tools.py     [NEW]
│   ├── canton_tools.py          [NEW]
│   └── template_parser.py       [NEW]
│
├── sandbox/
│   ├── daml_sandbox.py          [NEW - DamlSandbox class]
│   └── sandbox_manager.py       [NEW]
│
├── validators/
│   ├── syntax_validator.py      [NEW]
│   └── semantic_validator.py    [NEW]
│
├── canton/
│   ├── canton_client_v2.py      [NEW - v2 API client]
│   └── payload_builder.py       [NEW]
│
├── daml/
│   ├── template_builder.py      [NEW]
│   ├── choice_builder.py        [NEW]
│   └── error_classifier.py      [NEW]
│
└── pipeline/
    ├── orchestrator.py          [MODIFY - new workflow]
    ├── state.py                 [MODIFY - enhanced schema]
    └── tools_registry.py        [NEW]
```

---

## 3. CRITICAL TOOLS

### DAML Generation Tools (`backend/tools/daml_tools.py`)
```python
@tool
async def create_template(sandbox, name: str, fields: list) -> str:
    """Create template with fields"""

@tool
async def add_signatory(sandbox, template: str, party_field: str) -> str:
    """Add signatory declaration"""

@tool
async def add_choice(sandbox, template: str, choice_name: str, 
                     controller: str, params: list, body: str) -> str:
    """Add choice to template"""

@tool
async def validate_syntax(sandbox, file_path: str) -> str:
    """Pre-compile validation"""
```

### Compilation Tools (`backend/tools/compilation_tools.py`)
```python
@tool
async def compile_daml(sandbox) -> dict:
    """Run dpm build, return structured errors"""

@tool
async def run_daml_test(sandbox) -> dict:
    """Execute daml test"""
```

### Canton Tools (`backend/tools/canton_tools.py`)
```python
@tool
def extract_package_id(dar_path: str) -> str:
    """Parse DAR for package ID"""

@tool
async def upload_dar(client, dar_path: str) -> dict:
    """POST /v2/packages"""

@tool
async def allocate_party(client, hint: str) -> dict:
    """POST /v2/parties"""
```

---

## 4. DAML SANDBOX

```python
# backend/sandbox/daml_sandbox.py

class DamlSandbox:
    def __init__(self, project_id: str, project_name: str):
        self.sandbox_dir = f"/tmp/daml_sandboxes/{project_id}"
        self.commands = Commands(self.sandbox_dir)
        self.files = Files(self.sandbox_dir)
    
    async def initialize(self):
        # Create daml.yaml
        # Create daml/ directory
        # Create skeleton Main.daml

class Commands:
    async def run(self, cmd: str, timeout: int = 180) -> dict:
        # Execute shell command in sandbox
        # Return: {exit_code, stdout, stderr}

class Files:
    async def write(self, path: str, content: str):
    async def read(self, path: str) -> str:
    def list_files(self, pattern: str) -> list:
```

---

## 5. COMPILER LAYER

```python
# backend/daml/error_classifier.py

class ErrorClassifier:
    def parse_compile_output(self, stderr: str) -> list[dict]:
        """
        Parse DAML errors:
        File.daml:line:col: error message
        
        Returns: [
            {
                "file": "Main.daml",
                "line": 10,
                "type": "type_mismatch",
                "message": "...",
                "context": [...]
            }
        ]
        """
    
    def classify_error(self, msg: str) -> str:
        # type_mismatch, missing_signatory, parse_error,
        # unknown_variable, import_error, etc.
```

---

## 6. FIX AGENT REDESIGN

**Strategy Selection**:
```python
def select_fix_strategy(error: dict) -> str:
    if error["type"] == "type_mismatch":
        return "targeted_fix"  # Fix single line
    elif error["type"] == "import_error":
        return "add_import"    # Add import
    elif error["type"] == "missing_signatory":
        return "add_clause"    # Add signatory
    else:
        return "regenerate"    # Full rewrite
```

**Targeted Fix**:
- Read file, extract broken line
- LLM fixes ONLY that line
- Replace line in file
- No full file regeneration

---

## 7. CANTON DEPLOYMENT

```python
# backend/canton/canton_client_v2.py

class CantonClientV2:
    async def upload_dar(self, dar_path: str) -> (bool, str):
        # POST /v2/packages (binary DAR)
    
    async def allocate_party(self, hint: str) -> (bool, str, str):
        # POST /v2/parties
        # Returns: (success, party_id, error)
    
    async def create_contract(self, template_id: str, 
                              payload: dict, party: str) -> (bool, str, str):
        # POST /v2/commands/submit-and-wait-for-transaction
        # Returns: (success, contract_id, error)
    
    async def verify_contract(self, contract_id: str) -> (bool, str):
        # GET /v2/state/ledger-end
        # POST /v2/state/active-contracts
```

**Payload Builder**:
```python
# backend/canton/payload_builder.py

class PayloadBuilder:
    def __init__(self, template_code: str):
        self.fields = self._parse_template_fields()
    
    def build(self, party_values: dict) -> dict:
        # Parse template signature
        # Match field types to values
        # Return complete payload
```

---

## 8. IMPLEMENTATION PHASES

### **PHASE 1: Sandbox (3 days)**
**Create**:
- `backend/sandbox/daml_sandbox.py` (200 lines)
- `backend/sandbox/sandbox_manager.py` (80 lines)

**Test**: Create project, write files, run commands

---

### **PHASE 2: DAML Tools (5 days)**
**Create**:
- `backend/tools/daml_tools.py` (400 lines)
- `backend/daml/template_builder.py` (150 lines)
- `backend/daml/choice_builder.py` (100 lines)

**Test**: Use tools to build complete template

---

### **PHASE 3: Validators (3 days)**
**Create**:
- `backend/validators/syntax_validator.py` (200 lines)
- `backend/agents/syntax_validator.py` (80 lines)

**Test**: Detect syntax errors before compilation

---

### **PHASE 4: Compiler + Classifier (4 days)**
**Create**:
- `backend/daml/error_classifier.py` (250 lines)

**Modify**:
- `backend/agents/compile_agent.py` (add structured parsing)

**Test**: Compile broken DAML, get structured errors

---

### **PHASE 5: Fix Agent (5 days)**
**Modify**:
- `backend/agents/fix_agent.py` (complete rewrite - 300 lines)

**Test**: Fix type errors, syntax errors, missing imports

---

### **PHASE 6: Builder Agent (5 days)**
**Create**:
- `backend/agents/template_planner.py` (200 lines)
- `backend/agents/builder_agent.py` (250 lines)
- `backend/pipeline/tools_registry.py` (100 lines)

**Test**: ReAct agent builds template using tools

---

### **PHASE 7: Canton Deployment (4 days)**
**Create**:
- `backend/canton/canton_client_v2.py` (300 lines)
- `backend/canton/payload_builder.py` (150 lines)
- `backend/tools/canton_tools.py` (200 lines)

**Modify**:
- `backend/agents/deploy_agent.py` (rewrite - 200 lines)

**Test**: Upload DAR, create contract, verify

---

### **PHASE 8: Pipeline Integration (5 days)**
**Create**:
- `backend/agents/prompt_enhancer.py` (120 lines)
- `backend/agents/scenario_generator.py` (180 lines)
- `backend/agents/test_runner.py` (100 lines)

**Modify**:
- `backend/pipeline/orchestrator.py` (new workflow - 400 lines)
- `backend/pipeline/state.py` (enhanced schema - 100 lines)

**Test**: Full E2E pipeline

---

### **PHASE 9: Testing & Polish (4 days)**
- Integration tests
- Error recovery tests
- Performance optimization
- Documentation

---

## TOTAL: 38 days (7.6 weeks)

**Line Count Estimate**: ~5,000 new lines, ~1,000 modified lines

**Key Files by Priority**:
1. `daml_sandbox.py` - Foundation
2. `daml_tools.py` - Core generation
3. `error_classifier.py` - Error handling
4. `builder_agent.py` - Tool orchestration
5. `canton_client_v2.py` - Deployment
6. `orchestrator.py` - Workflow
