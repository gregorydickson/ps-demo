# Legal Contract Intelligence Platform - Claude Code Instructions

## Project Overview

AI-powered legal contract analysis platform for ProfitSolv. Analyzes legal contracts using multi-model AI routing, extracts risk factors, and enables natural language Q&A.

**Purpose:** Interview demonstration / Proof of Concept
**Repository:** https://github.com/gregorydickson/ps-demo

---

## Prime Directives

1. **Cost Optimization First**: Always use the cheapest appropriate model. Flash-Lite for simple tasks, Flash for balanced, Pro only for complex reasoning.

2. **TDD Methodology**: Follow Kent Beck's Red-Green-Refactor cycle. Write failing tests first, minimal implementation, then refactor.

3. **Tidy First**: Separate structural changes from behavioral changes. Never mix them in the same commit.

4. **FalkorDB, Not Neo4j**: The project uses FalkorDB (Redis-based graph DB), not Neo4j as originally planned. Port 6379 for graph, port 6380 for Redis cost tracking.

5. **Async Everything**: All I/O operations must be async. Use `asyncio.to_thread()` for blocking calls to external APIs (Gemini, LlamaParse).

6. **Mock External APIs in Tests**: Never make real API calls in tests. Use pytest fixtures from `backend/tests/conftest.py`.

---

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| AI Models | Google Gemini 2.5/3.0 | Multi-model routing via GeminiRouter |
| Document Parsing | LlamaParse v0.6.88 | Legal-specific PDF parsing |
| Agent Orchestration | LangGraph v1.0.3 | Stateful workflow management |
| Vector Storage | ChromaDB | Semantic search with text-embedding-004 |
| Graph Database | FalkorDB | Redis-based, Cypher-compatible |
| Cost Tracking | Redis (port 6380) | 30-day retention |
| Backend | FastAPI | Async Python API |
| Frontend | Next.js 14+ | App Router, TypeScript, Tailwind |

---

## Project Structure

```
ps-demo/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── services/
│   │   ├── gemini_router.py       # Multi-model AI routing (CRITICAL)
│   │   ├── cost_tracker.py        # Redis cost tracking
│   │   ├── vector_store.py        # ChromaDB operations
│   │   ├── graph_store.py         # FalkorDB operations
│   │   ├── llamaparse_service.py  # PDF parsing
│   │   └── api_resilience.py      # Circuit breaker, retry logic
│   ├── workflows/
│   │   ├── contract_analysis_workflow.py  # Full analysis workflow
│   │   └── qa_workflow.py                 # Lightweight Q&A (preferred for queries)
│   ├── models/
│   │   ├── schemas.py             # Pydantic request/response models
│   │   └── graph_schemas.py       # FalkorDB node/relationship models
│   ├── utils/
│   │   ├── logging.py             # Structured logging (structlog)
│   │   ├── request_context.py     # Request ID tracking
│   │   └── performance.py         # Execution time logging
│   └── tests/
│       ├── conftest.py            # Shared test fixtures
│       ├── unit/                  # Unit tests (59 tests)
│       └── integration/           # Integration tests (30 tests)
├── frontend/
│   ├── src/
│   │   ├── app/                   # Next.js App Router pages
│   │   ├── components/            # React components
│   │   ├── lib/api.ts             # API client
│   │   └── __tests__/             # Frontend tests (31 tests)
│   └── vitest.config.ts           # Test configuration
├── gcp/                           # GCP deployment configs
├── scripts/                       # Deployment scripts
├── docs/                          # Workplans and documentation
└── docker-compose.yml             # Dev infrastructure
```

---

## Key Files to Understand

### Backend Core
- `backend/services/gemini_router.py` - **START HERE**. Multi-model routing with TaskComplexity enum (SIMPLE/BALANCED/COMPLEX/REASONING). All AI interactions go through this.
- `backend/workflows/qa_workflow.py` - Lightweight Q&A workflow. Use this for queries, not the full workflow.
- `backend/main.py` - FastAPI app with all endpoints and middleware.

### Frontend Core
- `frontend/src/lib/api.ts` - API client with TypeScript types for all endpoints.
- `frontend/src/components/FileUpload.tsx` - PDF upload with drag-and-drop.
- `frontend/src/app/dashboard/[contractId]/page.tsx` - Main dashboard view.

### Configuration
- `.env.example` - Required environment variables
- `docker-compose.yml` - Development infrastructure (FalkorDB + Redis)
- `docker-compose.prod.yml` - Production configuration

---

## API Endpoints

| Method | Endpoint | Purpose | Workflow |
|--------|----------|---------|----------|
| POST | `/api/contracts/upload` | Upload & analyze PDF | Full workflow |
| POST | `/api/contracts/{id}/query` | Q&A on contract | QA workflow (fast) |
| GET | `/api/contracts/{id}` | Get contract details | FalkorDB query |
| GET | `/api/analytics/costs` | Cost breakdown | Redis query |
| GET | `/health` | Service health check | - |

---

## Model Routing (GeminiRouter)

```python
# TaskComplexity enum determines which model to use:
SIMPLE = "gemini-2.5-flash-lite"    # $0.04/M - Q&A, simple extraction
BALANCED = "gemini-2.5-flash"       # $0.075/M - Risk analysis, summaries
COMPLEX = "gemini-2.5-pro"          # $0.15/M - Deep reasoning
REASONING = "gemini-3-pro"          # Premium - Complex multi-step logic
```

**Cost Target:** ~$0.027 per contract (82% savings vs single premium model)

---

## Running the Project

### Development
```bash
# Start infrastructure
docker-compose up -d

# Backend (terminal 1)
cd backend
source venv/bin/activate
uvicorn main:app --reload

# Frontend (terminal 2)
cd frontend
npm run dev
```

### Testing
```bash
# Backend tests (120 tests)
cd backend
pytest tests/ -v

# Frontend tests (31 tests)
cd frontend
npm test
```

### Production Build
```bash
# Local production test
./scripts/local-prod-test.sh

# Deploy to GCP
./scripts/build-and-push.sh v1.0.0
./scripts/deploy-to-cloudrun.sh v1.0.0
```

---

## Environment Variables

**Required:**
```env
GOOGLE_API_KEY=your-gemini-api-key
LLAMA_CLOUD_API_KEY=your-llamaparse-key
REDIS_URL=redis://localhost:6380
FALKORDB_URL=redis://localhost:6379
```

**Optional:**
```env
LOG_LEVEL=INFO
LOG_FORMAT=json  # or "pretty" for development
```

---

## Common Tasks

### Adding a New Service
1. Create service file in `backend/services/`
2. Add unit tests in `backend/tests/unit/test_{service}_unit.py`
3. Use dependency injection pattern (pass dependencies to constructor)
4. Add to `main.py` initialization if needed

### Adding a New Endpoint
1. Add Pydantic models to `backend/models/schemas.py`
2. Add endpoint to `backend/main.py`
3. Add integration test in `backend/tests/integration/test_api_integration.py`
4. Update `frontend/src/lib/api.ts` with TypeScript types

### Adding a New Frontend Component
1. Create component in `frontend/src/components/`
2. Use React.memo for expensive renders
3. Add useEffect cleanup for async operations
4. Add test in `frontend/src/__tests__/components/`

---

## Architecture Patterns

### Retry Logic (Gemini calls)
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
async def generate(...):
    ...
```

### Circuit Breaker
```python
from backend.services.api_resilience import gemini_breaker

@gemini_breaker
async def external_api_call(...):
    ...
```

### Structured Logging
```python
from backend.utils.logging import get_logger
logger = get_logger("service_name")

logger.info("operation_complete", contract_id=id, cost=0.001)
```

### Request Tracking
All requests automatically get X-Request-ID header. Use `get_request_id()` from `backend.utils.request_context`.

---

## Workplan Status

| Part | Status | Description |
|------|--------|-------------|
| Part 1 | ✅ Complete | Core Services (GeminiRouter, CostTracker, LlamaParse) |
| Part 2 | ✅ Complete | Storage + Workflow (ChromaDB, FalkorDB, LangGraph) |
| Part 3 | ✅ Complete | FastAPI Backend (4 endpoints) |
| Part 4 | ✅ Complete | Next.js Frontend (9 components) |
| Part 5 | ✅ Complete | Testing Strategy (120 tests) |
| Part 6 | ✅ Complete | Architecture Improvements (resilience, observability) |
| Part 7 | ✅ Complete | GCP Deployment Prep (Dockerfiles, scripts) |

---

## Known Issues / Technical Debt

1. **Pydantic Deprecation**: Some v1 syntax used, should migrate to v2 syntax
2. **datetime.utcnow()**: Deprecated, should use `datetime.now(timezone.utc)`
3. **Frontend Test Dependencies**: Run `npm install` in frontend before running tests
4. **No Authentication**: POC has no auth - add before production use

---

## Quick Reference

### Model Costs (per 1M tokens)
| Model | Input | Output | Use For |
|-------|-------|--------|---------|
| Flash-Lite | $0.04 | $0.12 | Q&A, extraction |
| Flash | $0.075 | $0.30 | Risk analysis |
| Pro | $0.15 | $0.60 | Complex reasoning |

### Ports
| Service | Port |
|---------|------|
| Backend API | 8000 |
| Frontend | 3000 |
| FalkorDB (graph) | 6379 |
| Redis (cost tracking) | 6380 |

### Test Commands
```bash
pytest backend/tests/unit/ -v           # Unit tests only
pytest backend/tests/integration/ -v    # Integration tests
pytest --cov=backend --cov-report=html  # Coverage report
npm test -- --coverage                  # Frontend coverage
```

---

## Contact / Resources

- **Workplans:** `docs/1-workplan.md` and `docs/2-workplan-part*.md`
- **Deployment Guide:** `DEPLOYMENT.md`
- **Architecture Review:** `docs/3-workplan-part6-architecture.md`
