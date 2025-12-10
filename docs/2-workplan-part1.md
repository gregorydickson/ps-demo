# Part 1: Infrastructure & Core Services

## ✅ STATUS: COMPLETE

**Completed By:** Agent 3f2aab53
**Lines of Code:** ~1,630
**Tests:** 7/7 passing

### Completion Checklist
- [x] Task 1.1: Gemini Router Service - `backend/services/gemini_router.py`
- [x] Task 1.2: Cost Tracker Service - `backend/services/cost_tracker.py`
- [x] Task 1.3: LlamaParse Service - `backend/services/llamaparse_service.py`
- [x] Task 1.4: Pydantic Schemas - `backend/models/schemas.py`

### Post-Implementation Fixes Applied
- [x] Added `asyncio.to_thread()` for non-blocking Gemini API calls
- [x] API key no longer stored after `genai.configure()`

---

**Parallel Execution Group**: Can run independently
**Dependencies**: None (foundation layer)
**Estimated Effort**: 2-3 hours

---

## Scope

This part implements the foundational services that other parts depend on:
1. Gemini Router with multi-model cost optimization
2. Cost Tracker service (Redis-based)
3. LlamaParse integration for legal document parsing

---

## Task 1.1: Gemini Router Service

**File**: `backend/services/gemini_router.py`

### Requirements
- Implement `TaskComplexity` enum: SIMPLE, BALANCED, COMPLEX, REASONING
- Create `GeminiRouter` class with:
  - Model mapping for each complexity level
  - Cost tracking per model tier
  - `get_model()` method with thinking budget support
  - `generate()` async method with system instruction support
- Use model names:
  - SIMPLE: `gemini-2.5-flash-lite`
  - BALANCED: `gemini-2.5-flash`
  - COMPLEX: `gemini-2.5-pro`
  - REASONING: `gemini-3-pro`

### Success Criteria
- [ ] Can instantiate router and get appropriate model for each complexity
- [ ] Async generate method returns text, model name, token counts, and cost
- [ ] Cost calculation is accurate based on token counts

---

## Task 1.2: Cost Tracker Service

**File**: `backend/services/cost_tracker.py`

### Requirements
- Redis-based API cost tracking
- `track_api_call()` method to log:
  - Model name
  - Input/output tokens
  - Cost
  - Operation type
  - Timestamp
- `get_daily_costs()` method returning:
  - Total cost
  - Total tokens
  - Breakdown by model
  - Call counts
- 30-day data retention

### Success Criteria
- [ ] Can track API calls to Redis
- [ ] Can retrieve daily cost summaries
- [ ] Breakdown by model works correctly

---

## Task 1.3: LlamaParse Service

**File**: `backend/services/llamaparse_service.py`

### Requirements
- `LegalDocumentParser` class using LlamaParse v0.6.88
- Configure for legal documents with:
  - Markdown output format
  - Legal-specific parsing instructions
  - Table preservation
  - Section numbering
- Implement methods:
  - `parse_document()` - async PDF parsing
  - `_extract_sections()` - extract numbered legal sections
  - `_extract_tables()` - extract markdown tables
  - `_extract_metadata()` - extract dates, parties, contract type

### Success Criteria
- [ ] Can parse PDF bytes asynchronously
- [ ] Extracts sections with proper numbering
- [ ] Extracts contract metadata (dates, parties)
- [ ] Preserves table structures

---

## Task 1.4: Pydantic Schemas

**File**: `backend/models/schemas.py`

### Requirements
Define Pydantic models for:
- `ContractUploadResponse`
- `RiskAnalysis`
- `KeyTerms`
- `ContractQuery`
- `QueryResponse`
- `CostAnalytics`

### Success Criteria
- [ ] All schemas validate correctly
- [ ] JSON serialization works
- [ ] Proper type hints

---

## Integration Notes

- All services should be importable from `backend/services/`
- Use `python-dotenv` for environment variables
- Follow async patterns for I/O operations
- Include proper error handling and logging

---

## Testing Checklist

```bash
# After implementation, verify:
cd backend
python -c "from services.gemini_router import GeminiRouter, TaskComplexity; print('Router OK')"
python -c "from services.cost_tracker import CostTracker; print('Cost Tracker OK')"
python -c "from services.llamaparse_service import LegalDocumentParser; print('LlamaParse OK')"
python -c "from models.schemas import ContractUploadResponse; print('Schemas OK')"
```
