# Part 8: Enhanced Contract Analysis & API Expansion

## Overview

**Goal:** Integrate expert legal system instructions, add CRUD operations, enable cross-contract features, and prepare for production.

**Estimated Tasks:** 7 implementation tasks
**Prerequisites:** Parts 1-7 complete, expert legal instructions in GeminiRouter

---

## Task 1: Integrate Expert Legal Instructions into Workflows

### 1.1 Update Risk Analysis Node

**File:** `backend/workflows/contract_analysis_workflow.py`

**Change:** Replace basic prompt with `LegalExpertise.RISK_ANALYST`

```python
# FIND (around line 227-231):
response = await self.gemini_router.generate(
    prompt=prompt,
    model_name="gemini-flash",
    response_format="json"
)

# REPLACE WITH:
from ..services.gemini_router import LegalExpertise

response = await self.gemini_router.generate_with_expertise(
    prompt=prompt,
    expertise=LegalExpertise.RISK_ANALYST,
    additional_context=f"Contract: {state['filename']}"
)
```

### 1.2 Update QA Workflow

**File:** `backend/workflows/qa_workflow.py`

**Change:** Replace hardcoded system instruction

```python
# FIND (lines 131-135):
response = await self.gemini_router.generate(
    prompt=prompt,
    complexity=TaskComplexity.SIMPLE,
    system_instruction="You are a helpful legal assistant..."
)

# REPLACE WITH:
response = await self.gemini_router.generate_with_expertise(
    prompt=prompt,
    expertise=LegalExpertise.QA_ASSISTANT,
)
```

### 1.3 Add Tests

**File:** `backend/tests/unit/test_expert_integration.py` (NEW)

```python
import pytest
from unittest.mock import AsyncMock, patch
from backend.services.gemini_router import LegalExpertise

@pytest.mark.asyncio
async def test_risk_analysis_uses_expert():
    """Risk analysis should use RISK_ANALYST expertise."""
    with patch('backend.workflows.contract_analysis_workflow.GeminiRouter') as mock:
        mock_instance = mock.return_value
        mock_instance.generate_with_expertise = AsyncMock()
        # ... test implementation

@pytest.mark.asyncio
async def test_qa_uses_expert():
    """QA should use QA_ASSISTANT expertise."""
    # Similar test structure
```

---

## Task 2: List Contracts Endpoint

### 2.1 Add Schemas

**File:** `backend/models/schemas.py`

```python
class ContractSummary(BaseModel):
    """Summary for list view."""
    contract_id: str
    filename: str
    upload_date: datetime
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    party_count: int = 0

class ContractListResponse(BaseModel):
    """Paginated contract list."""
    contracts: List[ContractSummary]
    total: int
    page: int
    page_size: int
    has_more: bool
```

### 2.2 Add Graph Store Method

**File:** `backend/services/graph_store.py`

```python
async def list_contracts(
    self,
    skip: int = 0,
    limit: int = 20,
    risk_level: Optional[str] = None,
    sort_by: str = "upload_date",
    sort_order: str = "DESC"
) -> Tuple[List[Dict], int]:
    """List contracts with pagination."""

    where_clause = ""
    if risk_level:
        where_clause = f"WHERE c.risk_level = '{risk_level}'"

    # Count query
    count_query = f"""
        MATCH (c:Contract)
        {where_clause}
        RETURN count(c) as total
    """

    # Data query
    query = f"""
        MATCH (c:Contract)
        {where_clause}
        OPTIONAL MATCH (c)<-[:PARTY_TO]-(company:Company)
        RETURN c.contract_id, c.filename, c.upload_date,
               c.risk_score, c.risk_level,
               count(DISTINCT company) as party_count
        ORDER BY c.{sort_by} {sort_order}
        SKIP {skip} LIMIT {limit}
    """

    # Execute both queries
    # Return (contracts, total)
```

### 2.3 Add Endpoint

**File:** `backend/main.py`

```python
@app.get("/api/contracts", response_model=ContractListResponse, tags=["Contracts"])
async def list_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    risk_level: Optional[str] = Query(None, regex="^(low|medium|high)$"),
    sort_by: str = Query("upload_date", regex="^(upload_date|risk_score|filename)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    """List all contracts with pagination and filtering."""
    skip = (page - 1) * page_size

    contracts, total = await graph_store.list_contracts(
        skip=skip,
        limit=page_size,
        risk_level=risk_level,
        sort_by=sort_by,
        sort_order=sort_order.upper()
    )

    return ContractListResponse(
        contracts=[ContractSummary(**c) for c in contracts],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(skip + len(contracts)) < total
    )
```

---

## Task 3: Delete Contract Endpoint

### 3.1 Add Vector Store Delete

**File:** `backend/services/vector_store.py`

```python
async def delete_contract(self, contract_id: str) -> int:
    """Delete all chunks for a contract."""
    # Get IDs first
    results = self.collection.get(
        where={"contract_id": contract_id}
    )

    if results["ids"]:
        self.collection.delete(ids=results["ids"])

    return len(results["ids"])
```

### 3.2 Add Graph Store Delete

**File:** `backend/services/graph_store.py`

```python
async def delete_contract(self, contract_id: str) -> bool:
    """Delete contract and all related nodes."""
    query = """
        MATCH (c:Contract {contract_id: $contract_id})
        OPTIONAL MATCH (c)-[r]-()
        DELETE r, c
        RETURN count(c) as deleted
    """

    result = await asyncio.to_thread(
        self.graph.query,
        query,
        {"contract_id": contract_id}
    )

    return result.result_set[0][0] > 0
```

### 3.3 Add Endpoint

**File:** `backend/main.py`

```python
@app.delete("/api/contracts/{contract_id}", status_code=204, tags=["Contracts"])
async def delete_contract(
    contract_id: str = Path(..., description="Contract ID to delete")
):
    """Delete contract and all associated data."""
    # Check exists
    contract = await graph_store.get_contract_relationships(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Delete from both stores
    vector_store = ContractVectorStore()
    chunks_deleted = await vector_store.delete_contract(contract_id)
    await graph_store.delete_contract(contract_id)

    logger.info(f"Deleted contract {contract_id}, {chunks_deleted} chunks")
    return Response(status_code=204)
```

---

## Task 4: Global Search Endpoint

### 4.1 Add Vector Store Method

**File:** `backend/services/vector_store.py`

```python
async def global_search(
    self,
    query: str,
    n_results: int = 20,
    risk_level: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search across ALL contracts."""
    where_filter = {}
    if risk_level:
        where_filter["risk_level"] = risk_level

    results = await asyncio.to_thread(
        self.collection.query,
        query_texts=[query],
        n_results=n_results,
        where=where_filter if where_filter else None,
        include=["documents", "metadatas", "distances"]
    )

    # Group by contract_id
    grouped = {}
    for i, doc in enumerate(results["documents"][0]):
        cid = results["metadatas"][0][i]["contract_id"]
        if cid not in grouped:
            grouped[cid] = {"contract_id": cid, "matches": [], "best_score": 1.0}
        grouped[cid]["matches"].append({
            "text": doc[:200],
            "score": 1 - results["distances"][0][i]
        })
        grouped[cid]["best_score"] = min(
            grouped[cid]["best_score"],
            results["distances"][0][i]
        )

    return sorted(grouped.values(), key=lambda x: x["best_score"])
```

### 4.2 Add Endpoint

**File:** `backend/main.py`

```python
@app.get("/api/contracts/search", tags=["Contracts"])
async def search_contracts(
    query: str = Query(..., min_length=3),
    limit: int = Query(10, ge=1, le=50),
    risk_level: Optional[str] = Query(None)
):
    """Search across all contracts."""
    vector_store = ContractVectorStore()

    results = await vector_store.global_search(
        query=query,
        n_results=limit * 3,  # Get more, then dedupe
        risk_level=risk_level
    )

    # Enrich with graph data
    enriched = []
    for r in results[:limit]:
        contract = await graph_store.get_contract_relationships(r["contract_id"])
        if contract:
            enriched.append({
                "contract_id": r["contract_id"],
                "filename": contract.contract.filename,
                "risk_level": contract.contract.risk_level,
                "matches": r["matches"][:3],
                "relevance_score": 1 - r["best_score"]
            })

    return {"query": query, "results": enriched, "total": len(enriched)}
```

---

## Task 5: Contract Comparison Endpoint

### 5.1 Add Comparison Service

**File:** `backend/services/contract_comparison.py` (NEW)

```python
"""Contract comparison using expert legal analysis."""

from typing import List, Dict, Any, Optional
from ..services.gemini_router import GeminiRouter, LegalExpertise
from ..services.vector_store import ContractVectorStore
from ..services.graph_store import ContractGraphStore

class ContractComparisonService:
    """Compare two contracts using AI analysis."""

    def __init__(
        self,
        gemini_router: GeminiRouter,
        vector_store: ContractVectorStore,
        graph_store: ContractGraphStore
    ):
        self.gemini_router = gemini_router
        self.vector_store = vector_store
        self.graph_store = graph_store

    async def compare(
        self,
        contract_id_a: str,
        contract_id_b: str,
        aspects: List[str]
    ) -> Dict[str, Any]:
        """Compare contracts across specified aspects."""

        # Get graph data
        graph_a = await self.graph_store.get_contract_relationships(contract_id_a)
        graph_b = await self.graph_store.get_contract_relationships(contract_id_b)

        comparisons = []
        total_cost = 0.0

        for aspect in aspects:
            # Get relevant chunks for each contract
            chunks_a = await self.vector_store.semantic_search(
                query=aspect, contract_id=contract_id_a, n_results=3
            )
            chunks_b = await self.vector_store.semantic_search(
                query=aspect, contract_id=contract_id_b, n_results=3
            )

            # Build comparison prompt
            prompt = self._build_comparison_prompt(
                aspect=aspect,
                contract_a_name=graph_a.contract.filename,
                contract_b_name=graph_b.contract.filename,
                chunks_a=chunks_a,
                chunks_b=chunks_b
            )

            # Use CONTRACT_REVIEWER expertise
            result = await self.gemini_router.generate_with_expertise(
                prompt=prompt,
                expertise=LegalExpertise.CONTRACT_REVIEWER,
            )

            comparisons.append({
                "aspect": aspect,
                "analysis": result.text,
                "cost": result.cost
            })
            total_cost += result.cost

        return {
            "contract_a": {"id": contract_id_a, "filename": graph_a.contract.filename},
            "contract_b": {"id": contract_id_b, "filename": graph_b.contract.filename},
            "comparisons": comparisons,
            "total_cost": total_cost
        }

    def _build_comparison_prompt(
        self, aspect: str, contract_a_name: str, contract_b_name: str,
        chunks_a: List, chunks_b: List
    ) -> str:
        context_a = "\n".join([c["text"][:500] for c in chunks_a])
        context_b = "\n".join([c["text"][:500] for c in chunks_b])

        return f"""Compare these two contracts on: {aspect}

CONTRACT A ({contract_a_name}):
{context_a}

CONTRACT B ({contract_b_name}):
{context_b}

Provide:
1. Summary of {aspect} in Contract A
2. Summary of {aspect} in Contract B
3. Key differences
4. Risk implications of differences
5. Recommendation"""
```

### 5.2 Add Schemas

**File:** `backend/models/schemas.py`

```python
class ContractComparisonRequest(BaseModel):
    contract_id_a: str
    contract_id_b: str
    aspects: List[str] = ["payment_terms", "liability", "termination", "indemnification"]

class ContractComparisonResponse(BaseModel):
    contract_a: Dict[str, str]
    contract_b: Dict[str, str]
    comparisons: List[Dict[str, Any]]
    total_cost: float
```

### 5.3 Add Endpoint

**File:** `backend/main.py`

```python
@app.post("/api/contracts/compare", tags=["Contracts"])
async def compare_contracts(request: ContractComparisonRequest):
    """Compare two contracts across specified aspects."""
    from backend.services.contract_comparison import ContractComparisonService

    service = ContractComparisonService(
        gemini_router=qa_workflow.gemini_router,
        vector_store=ContractVectorStore(),
        graph_store=graph_store
    )

    return await service.compare(
        contract_id_a=request.contract_id_a,
        contract_id_b=request.contract_id_b,
        aspects=request.aspects
    )
```

---

## Task 6: Batch Upload Endpoint

### 6.1 Add Schemas

**File:** `backend/models/schemas.py`

```python
class BatchUploadResult(BaseModel):
    filename: str
    contract_id: Optional[str] = None
    status: str  # "success" | "failed"
    error: Optional[str] = None
    risk_level: Optional[str] = None

class BatchUploadResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: List[BatchUploadResult]
    total_cost: float
    processing_time_ms: float
```

### 6.2 Add Endpoint

**File:** `backend/main.py`

```python
@app.post("/api/contracts/batch-upload", response_model=BatchUploadResponse, tags=["Contracts"])
async def batch_upload(
    files: List[UploadFile] = File(..., description="PDF files (max 5)")
):
    """Upload and analyze multiple contracts concurrently."""
    import asyncio

    if len(files) > 5:
        raise HTTPException(400, "Maximum 5 files per batch")

    # Validate all are PDFs
    for f in files:
        if not f.filename.endswith('.pdf'):
            raise HTTPException(400, f"Invalid file type: {f.filename}")

    start_time = time.time()

    async def process_one(file: UploadFile) -> BatchUploadResult:
        try:
            contract_id = str(uuid.uuid4())
            file_bytes = await file.read()

            result = await workflow.run(
                contract_id=contract_id,
                file_bytes=file_bytes,
                filename=file.filename
            )

            return BatchUploadResult(
                filename=file.filename,
                contract_id=contract_id,
                status="success",
                risk_level=result.get("risk_analysis", {}).get("risk_level")
            )
        except Exception as e:
            return BatchUploadResult(
                filename=file.filename,
                status="failed",
                error=str(e)
            )

    # Process concurrently
    results = await asyncio.gather(*[process_one(f) for f in files])

    successful = sum(1 for r in results if r.status == "success")

    return BatchUploadResponse(
        total=len(files),
        successful=successful,
        failed=len(files) - successful,
        results=results,
        total_cost=0.0,  # Would aggregate from results
        processing_time_ms=(time.time() - start_time) * 1000
    )
```

---

## Task 7: Update Frontend API Client

### 7.1 Add TypeScript Types

**File:** `frontend/src/lib/api.ts`

```typescript
// Add to existing types

export interface ContractSummary {
  contract_id: string;
  filename: string;
  upload_date: string;
  risk_score: number | null;
  risk_level: string | null;
  party_count: number;
}

export interface ContractListResponse {
  contracts: ContractSummary[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface SearchResult {
  contract_id: string;
  filename: string;
  risk_level: string | null;
  matches: Array<{ text: string; score: number }>;
  relevance_score: number;
}

export interface ComparisonRequest {
  contract_id_a: string;
  contract_id_b: string;
  aspects?: string[];
}
```

### 7.2 Add API Methods

**File:** `frontend/src/lib/api.ts`

```typescript
// Add to API class

async listContracts(params: {
  page?: number;
  page_size?: number;
  risk_level?: string;
  sort_by?: string;
  sort_order?: string;
}): Promise<ContractListResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set('page', String(params.page));
  if (params.page_size) query.set('page_size', String(params.page_size));
  if (params.risk_level) query.set('risk_level', params.risk_level);
  if (params.sort_by) query.set('sort_by', params.sort_by);
  if (params.sort_order) query.set('sort_order', params.sort_order);

  const res = await fetch(`${this.baseUrl}/api/contracts?${query}`);
  return res.json();
}

async deleteContract(contractId: string): Promise<void> {
  await fetch(`${this.baseUrl}/api/contracts/${contractId}`, {
    method: 'DELETE'
  });
}

async searchContracts(query: string, limit?: number): Promise<{ results: SearchResult[] }> {
  const params = new URLSearchParams({ query });
  if (limit) params.set('limit', String(limit));

  const res = await fetch(`${this.baseUrl}/api/contracts/search?${params}`);
  return res.json();
}

async compareContracts(request: ComparisonRequest): Promise<any> {
  const res = await fetch(`${this.baseUrl}/api/contracts/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  return res.json();
}
```

---

## Implementation Order

1. **Task 1** - Expert instructions (foundation)
2. **Task 2** - List contracts (needed for UI)
3. **Task 3** - Delete contract (cleanup)
4. **Task 4** - Global search (cross-contract)
5. **Task 5** - Comparison (advanced)
6. **Task 6** - Batch upload (efficiency)
7. **Task 7** - Frontend API (UI support)

---

## Testing Checklist

For each task, run:

```bash
# Unit tests
pytest backend/tests/unit/ -v -k "test_name"

# Integration tests (requires Docker)
python3 backend/scripts/run_integration_tests.py

# Frontend tests
cd frontend && npm test
```

---

## API Summary After Part 8

| Method | Endpoint | New |
|--------|----------|-----|
| POST | `/api/contracts/upload` | |
| POST | `/api/contracts/batch-upload` | ✅ |
| GET | `/api/contracts` | ✅ |
| GET | `/api/contracts/search` | ✅ |
| GET | `/api/contracts/{id}` | |
| POST | `/api/contracts/{id}/query` | |
| POST | `/api/contracts/compare` | ✅ |
| DELETE | `/api/contracts/{id}` | ✅ |
| GET | `/api/analytics/costs` | |
| GET | `/health` | |