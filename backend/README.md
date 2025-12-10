# Legal Contract Intelligence Platform - Backend

FastAPI backend for AI-powered legal contract analysis.

## Quick Start

```bash
# Prerequisites: Docker running, .env configured

# Start infrastructure
docker-compose up -d

# Setup Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run API
uvicorn main:app --reload
```

**API available at:** http://localhost:8000
**Interactive docs:** http://localhost:8000/docs

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
├─────────────────────────────────────────────────────────────┤
│  POST /api/contracts/upload    → Contract Analysis          │
│  POST /api/contracts/{id}/query → Q&A                       │
│  GET  /api/contracts/{id}      → Contract Details           │
│  GET  /api/analytics/costs     → Cost Tracking              │
├─────────────────────────────────────────────────────────────┤
│                    Service Layer                             │
│  • GeminiRouter (AI routing)   • CostTracker (Redis)        │
│  • ContractVectorStore (ChromaDB)                           │
│  • ContractGraphStore (FalkorDB)                            │
│  • LegalDocumentParser (LlamaParse)                         │
├─────────────────────────────────────────────────────────────┤
│                    Workflow Layer                            │
│  • ContractAnalysisWorkflow (LangGraph)                     │
│  • QAWorkflow (lightweight queries)                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Services

### GeminiRouter (`services/gemini_router.py`)

Routes requests to appropriate Gemini model based on task complexity:

```python
from services.gemini_router import GeminiRouter, TaskComplexity

router = GeminiRouter(api_key=GOOGLE_API_KEY)

result = await router.generate(
    prompt="Analyze this contract...",
    complexity=TaskComplexity.BALANCED
)
print(f"Model: {result.model_name}, Cost: ${result.cost:.6f}")
```

| Complexity | Model | Cost/1M tokens | Use Case |
|------------|-------|----------------|----------|
| `SIMPLE` | gemini-2.5-flash-lite | $0.04 | Quick extraction |
| `BALANCED` | gemini-2.5-flash | $0.075 | Standard Q&A |
| `COMPLEX` | gemini-2.5-pro | $0.15 | Deep analysis |
| `REASONING` | gemini-3-pro | Premium | Multi-step reasoning |

### CostTracker (`services/cost_tracker.py`)

Redis-based cost tracking with 30-day retention:

```python
from services.cost_tracker import CostTracker

tracker = CostTracker(redis_url=REDIS_URL)
tracker.track_api_call(
    model_name="gemini-2.5-flash",
    input_tokens=1000,
    output_tokens=500,
    cost=0.001,
    operation_type="query"
)

daily = tracker.get_daily_costs()
print(f"Today: ${daily['total_cost']:.4f}")
```

### ContractGraphStore (`services/graph_store.py`)

FalkorDB graph storage for contract relationships:

```python
from services.graph_store import ContractGraphStore

store = ContractGraphStore(host="localhost", port=6379)
await store.store_contract(contract, companies, clauses, risk_factors)
result = await store.get_contract_relationships(contract_id)
```

### ContractVectorStore (`services/vector_store.py`)

ChromaDB semantic search:

```python
from services.vector_store import ContractVectorStore

vector_store = ContractVectorStore()
await vector_store.store_document_sections(contract_id, text, metadata)
results = await vector_store.search(query, contract_id=contract_id)
```

---

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### Upload Contract
```bash
curl -X POST http://localhost:8000/api/contracts/upload \
  -F "file=@contract.pdf"
```

**Response:**
```json
{
  "contract_id": "uuid",
  "risk_analysis": {
    "risk_score": 6.5,
    "risk_level": "medium",
    "concerning_clauses": [...]
  },
  "total_cost": 0.0234
}
```

### Query Contract
```bash
curl -X POST http://localhost:8000/api/contracts/{id}/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the payment terms?"}'
```

### Get Contract Details
```bash
curl http://localhost:8000/api/contracts/{id}
```

### Cost Analytics
```bash
curl http://localhost:8000/api/analytics/costs
curl http://localhost:8000/api/analytics/costs?date=2024-12-10
```

---

## Testing

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests (requires FalkorDB)
python scripts/run_integration_tests.py

# With coverage
pytest --cov=. --cov-report=html
```

---

## Project Structure

```
backend/
├── main.py                 # FastAPI application
├── services/
│   ├── gemini_router.py    # AI model routing
│   ├── cost_tracker.py     # Redis cost tracking
│   ├── vector_store.py     # ChromaDB operations
│   ├── graph_store.py      # FalkorDB operations
│   ├── llamaparse_service.py # PDF parsing
│   └── api_resilience.py   # Circuit breaker, retry
├── workflows/
│   ├── contract_analysis_workflow.py
│   └── qa_workflow.py
├── models/
│   ├── schemas.py          # API schemas
│   └── graph_schemas.py    # Graph node schemas
├── utils/
│   ├── logging.py          # Structured logging
│   ├── request_context.py  # Request ID tracking
│   └── performance.py      # Timing decorators
├── scripts/
│   ├── run_integration_tests.py  # Visual test runner
│   └── import_test_documents.py  # Document import utility
└── tests/
    ├── unit/               # Unit tests
    └── integration/        # Integration tests
```

---

## Environment Variables

```bash
# Required
GOOGLE_API_KEY=your-gemini-api-key
LLAMA_CLOUD_API_KEY=your-llamaparse-key
REDIS_URL=redis://localhost:6380
FALKORDB_URL=redis://localhost:6379

# Optional
LOG_LEVEL=INFO
LOG_FORMAT=json  # or "pretty"
```

---

## Development

### Adding a New Service

1. Create `services/new_service.py`
2. Add unit tests in `tests/unit/test_new_service_unit.py`
3. Use dependency injection (pass deps to constructor)
4. Initialize in `main.py` if needed

### Adding a New Endpoint

1. Add Pydantic models to `models/schemas.py`
2. Add endpoint to `main.py`
3. Add integration test in `tests/integration/`
4. Update `frontend/src/lib/api.ts`

### Architecture Patterns

**Retry Logic:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
async def external_call():
    ...
```

**Circuit Breaker:**
```python
from services.api_resilience import gemini_breaker

@gemini_breaker
async def api_call():
    ...
```

**Structured Logging:**
```python
from utils.logging import get_logger
logger = get_logger("service_name")
logger.info("operation_complete", contract_id=id, cost=0.001)
```

---

## Ports

| Service | Port |
|---------|------|
| Backend API | 8000 |
| FalkorDB | 6379 |
| Redis (costs) | 6380 |
| ChromaDB | 8001 |

---

## Security Notes

**Development only - add before production:**
- Authentication (JWT/OAuth2)
- Rate limiting
- CORS restrictions
- HTTPS
- Input sanitization
