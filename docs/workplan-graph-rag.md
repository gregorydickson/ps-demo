# Graph RAG Implementation Workplan

## Overview

Implement Graph RAG (Retrieval-Augmented Generation) combining semantic vector search with graph traversal for enhanced contract Q&A. This approach retrieves relevant context through both semantic similarity AND relationship traversal, providing richer context for LLM generation.

**Current State:**
- Semantic search: ChromaDB with Google text-embedding-004
- Graph store: FalkorDB with Contract, Company, Clause, RiskFactor nodes
- Relationships: PARTY_TO, CONTAINS, HAS_RISK

**Target State:**
- Hybrid retrieval combining vector similarity + graph context
- Graph-aware context expansion (traverse related entities)
- Re-ranked results using Reciprocal Rank Fusion (RRF)

---

## Task 1: Graph Context Retriever

**File:** `backend/services/graph_context_retriever.py`

### Implementation

```python
"""
Graph context retrieval for Graph RAG.

Traverses FalkorDB to expand context around semantic search results.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GraphContext:
    """Context retrieved from graph traversal."""
    contract_id: str
    contract_metadata: Dict[str, Any]
    companies: List[Dict[str, Any]]
    related_clauses: List[Dict[str, Any]]
    risk_factors: List[Dict[str, Any]]
    traversal_depth: int


class GraphContextRetriever:
    """
    Retrieves expanded context from FalkorDB graph.

    Given a contract_id or clause, traverses the graph to gather:
    - Contract metadata (risk_score, payment_terms, etc.)
    - Connected companies and their roles
    - Related clauses (by type or section)
    - Associated risk factors
    """

    def __init__(self, graph_store):
        """
        Args:
            graph_store: ContractGraphStore instance
        """
        self.graph_store = graph_store
        self.graph = graph_store.graph

    async def get_context_for_contract(
        self,
        contract_id: str,
        include_companies: bool = True,
        include_clauses: bool = True,
        include_risks: bool = True,
        max_clauses: int = 10
    ) -> GraphContext:
        """
        Retrieve full graph context for a contract.

        Args:
            contract_id: Contract to get context for
            include_companies: Include connected companies
            include_clauses: Include contract clauses
            include_risks: Include risk factors
            max_clauses: Maximum clauses to return

        Returns:
            GraphContext with all related entities
        """
        # Implementation: Single Cypher query with OPTIONAL MATCH
        pass

    async def get_context_for_clause_type(
        self,
        contract_id: str,
        clause_type: str
    ) -> Dict[str, Any]:
        """
        Get context specific to a clause type (payment, termination, etc.).

        Returns clause content + related risks for that clause type.
        """
        # Implementation: Query clauses by type, join with risks
        pass

    async def find_similar_contracts_by_company(
        self,
        company_name: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find other contracts involving the same company.

        Useful for cross-contract analysis.
        """
        # Implementation: Match company, traverse to contracts
        pass

    async def get_risk_context(
        self,
        contract_id: str,
        risk_level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all risk factors with their associated clauses.

        Args:
            contract_id: Contract to query
            risk_level: Optional filter (low, medium, high)
        """
        # Implementation: Match risks, optionally filter by level
        pass
```

### Cypher Queries to Implement

```cypher
// get_context_for_contract - Single query for all context
MATCH (c:Contract {contract_id: $contract_id})
OPTIONAL MATCH (co:Company)-[:PARTY_TO]->(c)
OPTIONAL MATCH (c)-[:CONTAINS]->(cl:Clause)
OPTIONAL MATCH (c)-[:HAS_RISK]->(r:RiskFactor)
RETURN c,
       collect(DISTINCT co) as companies,
       collect(DISTINCT cl)[0..$max_clauses] as clauses,
       collect(DISTINCT r) as risks

// get_context_for_clause_type
MATCH (c:Contract {contract_id: $contract_id})-[:CONTAINS]->(cl:Clause)
WHERE cl.clause_type = $clause_type
OPTIONAL MATCH (c)-[:HAS_RISK]->(r:RiskFactor)
WHERE r.section = cl.section_name
RETURN cl, collect(r) as related_risks

// find_similar_contracts_by_company
MATCH (co:Company {name: $company_name})-[:PARTY_TO]->(c:Contract)
RETURN c.contract_id, c.filename, c.risk_level, co.role
ORDER BY c.upload_date DESC
LIMIT $limit

// get_risk_context
MATCH (c:Contract {contract_id: $contract_id})-[:HAS_RISK]->(r:RiskFactor)
WHERE $risk_level IS NULL OR r.risk_level = $risk_level
OPTIONAL MATCH (c)-[:CONTAINS]->(cl:Clause)
WHERE cl.section_name = r.section
RETURN r, cl.content as clause_content
```

### Success Criteria
- [x] All 4 methods implemented with async support
- [x] Single Cypher query per method (no N+1)
- [x] Unit tests with mocked FalkorDB (12 tests, all passing)
- [x] Returns empty results gracefully (no errors on missing data)

### Implementation Notes
- **Completed:** 2024-01-15
- **File:** `backend/services/graph_context_retriever.py`
- **Tests:** `backend/tests/unit/test_graph_context_retriever_unit.py`
- **Test Results:** 12/12 tests passing
- All methods use `asyncio.to_thread()` for FalkorDB queries
- Single Cypher query per method (no N+1 problems)
- Graceful handling of missing data (returns None or empty lists)
- Structured logging with structlog

---

## Task 2: Hybrid Retriever Service

**File:** `backend/services/hybrid_retriever.py`

### Implementation

```python
"""
Hybrid retriever combining semantic search with graph context.

Implements Graph RAG pattern:
1. Semantic search finds relevant text chunks
2. Graph traversal expands context with related entities
3. Results merged and re-ranked using RRF
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Single retrieval result with combined scores."""
    contract_id: str
    content: str
    source: str  # "semantic" | "graph"
    semantic_score: Optional[float] = None
    graph_relevance: Optional[float] = None
    rrf_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HybridRetrievalResponse:
    """Combined retrieval response."""
    results: List[RetrievalResult]
    semantic_count: int
    graph_count: int
    total_tokens_estimate: int


class HybridRetriever:
    """
    Combines vector search with graph traversal for Graph RAG.

    Retrieval Strategy:
    1. Run semantic search on query -> get top-k chunks
    2. Extract contract_ids from semantic results
    3. For each contract_id, fetch graph context
    4. Merge semantic chunks with graph context
    5. Re-rank using Reciprocal Rank Fusion (RRF)
    """

    def __init__(
        self,
        vector_store,
        graph_context_retriever,
        rrf_k: int = 60
    ):
        """
        Args:
            vector_store: ContractVectorStore instance
            graph_context_retriever: GraphContextRetriever instance
            rrf_k: RRF constant (default 60, standard value)
        """
        self.vector_store = vector_store
        self.graph_retriever = graph_context_retriever
        self.rrf_k = rrf_k

    async def retrieve(
        self,
        query: str,
        contract_id: Optional[str] = None,
        n_semantic: int = 5,
        n_graph: int = 3,
        include_companies: bool = True,
        include_risks: bool = True
    ) -> HybridRetrievalResponse:
        """
        Perform hybrid retrieval combining semantic + graph.

        Args:
            query: User's question
            contract_id: Optional specific contract (None = global search)
            n_semantic: Number of semantic results
            n_graph: Max graph context items per contract
            include_companies: Include company context from graph
            include_risks: Include risk factors from graph

        Returns:
            HybridRetrievalResponse with merged, re-ranked results
        """
        # Step 1: Semantic search
        semantic_results = await self.vector_store.semantic_search(
            query=query,
            n_results=n_semantic,
            contract_id=contract_id
        )

        # Step 2: Extract unique contract IDs
        contract_ids = set(r["metadata"]["contract_id"] for r in semantic_results)

        # Step 3: Fetch graph context for each contract (parallel)
        graph_contexts = await self._fetch_graph_contexts(
            contract_ids=contract_ids,
            include_companies=include_companies,
            include_risks=include_risks,
            max_items=n_graph
        )

        # Step 4: Convert to RetrievalResults
        all_results = self._merge_results(semantic_results, graph_contexts)

        # Step 5: Re-rank with RRF
        ranked_results = self._rrf_rerank(all_results)

        return HybridRetrievalResponse(
            results=ranked_results,
            semantic_count=len(semantic_results),
            graph_count=sum(len(gc) for gc in graph_contexts.values()),
            total_tokens_estimate=self._estimate_tokens(ranked_results)
        )

    async def _fetch_graph_contexts(
        self,
        contract_ids: set,
        include_companies: bool,
        include_risks: bool,
        max_items: int
    ) -> Dict[str, List[Dict]]:
        """Fetch graph context for multiple contracts in parallel."""
        # Use asyncio.gather for parallel fetching
        pass

    def _merge_results(
        self,
        semantic_results: List[Dict],
        graph_contexts: Dict[str, List[Dict]]
    ) -> List[RetrievalResult]:
        """Convert and merge semantic + graph results."""
        pass

    def _rrf_rerank(
        self,
        results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """
        Re-rank results using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank_i)) for each ranking list
        """
        # Sort semantic results by semantic_score
        # Sort graph results by graph_relevance
        # Calculate RRF score for each result
        # Return sorted by RRF score descending
        pass

    def _estimate_tokens(self, results: List[RetrievalResult]) -> int:
        """Estimate token count for context (chars / 4 approximation)."""
        return sum(len(r.content) for r in results) // 4
```

### RRF Algorithm

```python
def _rrf_rerank(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
    """
    Reciprocal Rank Fusion implementation.

    For each result, calculate: RRF = 1/(k + rank_semantic) + 1/(k + rank_graph)
    Results appearing in only one list get score from that list only.
    """
    # Create ranking for semantic results (by semantic_score desc)
    semantic_ranked = sorted(
        [r for r in results if r.semantic_score is not None],
        key=lambda x: x.semantic_score,
        reverse=True
    )
    semantic_ranks = {r.content: i + 1 for i, r in enumerate(semantic_ranked)}

    # Create ranking for graph results (by graph_relevance desc)
    graph_ranked = sorted(
        [r for r in results if r.graph_relevance is not None],
        key=lambda x: x.graph_relevance,
        reverse=True
    )
    graph_ranks = {r.content: i + 1 for i, r in enumerate(graph_ranked)}

    # Calculate RRF scores
    for result in results:
        rrf = 0.0
        if result.content in semantic_ranks:
            rrf += 1.0 / (self.rrf_k + semantic_ranks[result.content])
        if result.content in graph_ranks:
            rrf += 1.0 / (self.rrf_k + graph_ranks[result.content])
        result.rrf_score = rrf

    # Sort by RRF score descending
    return sorted(results, key=lambda x: x.rrf_score, reverse=True)
```

### Success Criteria
- [x] retrieve() combines semantic + graph results
- [x] RRF re-ranking implemented correctly
- [x] Parallel graph context fetching with asyncio.gather
- [x] Token estimation for context window management
- [x] Unit tests covering merge and rerank logic (23 tests, all passing)

### Implementation Notes
- **Completed:** 2024-01-15
- **File:** `backend/services/hybrid_retriever.py` (358 lines)
- **Tests:** `backend/tests/unit/test_hybrid_retriever_unit.py` (599 lines, 23 tests)
- **Test Results:** 23/23 tests passing
- Implements RRF formula: score = 1/(k + rank_semantic) + 1/(k + rank_graph)
- Uses asyncio.gather() for parallel graph context fetching
- Token estimation: chars/4 approximation
- Graceful handling of empty results and edge cases

---

## Task 3: Graph RAG Workflow

**File:** `backend/workflows/graph_rag_workflow.py`

### Implementation

```python
"""
Graph RAG workflow for enhanced contract Q&A.

Replaces simple QAWorkflow with graph-augmented retrieval.
"""

import os
from typing import TypedDict, Optional, List
import structlog

try:
    from ..services.hybrid_retriever import HybridRetriever, HybridRetrievalResponse
    from ..services.graph_context_retriever import GraphContextRetriever
    from ..services.vector_store import ContractVectorStore
    from ..services.graph_store import ContractGraphStore
    from ..services.gemini_router import GeminiRouter, TaskComplexity, LegalExpertise
    from ..services.cost_tracker import CostTracker
except ImportError:
    from backend.services.hybrid_retriever import HybridRetriever, HybridRetrievalResponse
    from backend.services.graph_context_retriever import GraphContextRetriever
    from backend.services.vector_store import ContractVectorStore
    from backend.services.graph_store import ContractGraphStore
    from backend.services.gemini_router import GeminiRouter, TaskComplexity, LegalExpertise
    from backend.services.cost_tracker import CostTracker

logger = structlog.get_logger()


class GraphRAGState(TypedDict):
    """State for Graph RAG workflow."""
    contract_id: Optional[str]
    query: str
    retrieval_response: Optional[HybridRetrievalResponse]
    context_text: str
    answer: Optional[str]
    sources: List[dict]
    cost: float
    error: Optional[str]


class GraphRAGWorkflow:
    """
    Graph RAG workflow combining hybrid retrieval with LLM generation.

    Flow:
    1. Hybrid retrieval (semantic + graph)
    2. Context formatting with source attribution
    3. LLM generation with legal expertise
    4. Response with sources
    """

    def __init__(
        self,
        vector_store: Optional[ContractVectorStore] = None,
        graph_store: Optional[ContractGraphStore] = None,
        gemini_router: Optional[GeminiRouter] = None,
        cost_tracker: Optional[CostTracker] = None
    ):
        self.vector_store = vector_store or ContractVectorStore()
        self.graph_store = graph_store or ContractGraphStore()
        self.gemini_router = gemini_router or GeminiRouter(
            api_key=os.getenv("GOOGLE_API_KEY")
        )
        self.cost_tracker = cost_tracker

        # Initialize hybrid retriever
        self.graph_retriever = GraphContextRetriever(self.graph_store)
        self.hybrid_retriever = HybridRetriever(
            vector_store=self.vector_store,
            graph_context_retriever=self.graph_retriever
        )

        logger.info("GraphRAGWorkflow initialized")

    async def run(
        self,
        query: str,
        contract_id: Optional[str] = None,
        n_results: int = 5,
        include_sources: bool = True
    ) -> GraphRAGState:
        """
        Execute Graph RAG workflow.

        Args:
            query: User's question
            contract_id: Optional specific contract (None = search all)
            n_results: Number of context items to retrieve
            include_sources: Whether to include source attribution

        Returns:
            GraphRAGState with answer, sources, and cost
        """
        state: GraphRAGState = {
            "contract_id": contract_id,
            "query": query,
            "retrieval_response": None,
            "context_text": "",
            "answer": None,
            "sources": [],
            "cost": 0.0,
            "error": None
        }

        try:
            # Step 1: Hybrid retrieval
            state = await self._retrieve(state, n_results)

            # Step 2: Format context
            state = self._format_context(state)

            # Step 3: Generate answer
            state = await self._generate(state)

            # Step 4: Extract sources
            if include_sources:
                state = self._extract_sources(state)

        except Exception as e:
            logger.error("graph_rag_error", error=str(e))
            state["error"] = str(e)

        return state

    async def _retrieve(self, state: GraphRAGState, n_results: int) -> GraphRAGState:
        """Step 1: Hybrid retrieval."""
        logger.info("graph_rag_retrieve", query=state["query"][:50])

        response = await self.hybrid_retriever.retrieve(
            query=state["query"],
            contract_id=state["contract_id"],
            n_semantic=n_results,
            n_graph=3,
            include_companies=True,
            include_risks=True
        )

        state["retrieval_response"] = response
        logger.info(
            "graph_rag_retrieved",
            semantic_count=response.semantic_count,
            graph_count=response.graph_count,
            total_results=len(response.results)
        )

        return state

    def _format_context(self, state: GraphRAGState) -> str:
        """Step 2: Format retrieved context for LLM."""
        if not state["retrieval_response"]:
            return state

        context_parts = []
        for i, result in enumerate(state["retrieval_response"].results, 1):
            source_type = "Document" if result.source == "semantic" else "Knowledge Graph"
            context_parts.append(
                f"[Source {i} - {source_type}]\n{result.content}\n"
            )

        state["context_text"] = "\n".join(context_parts)
        return state

    async def _generate(self, state: GraphRAGState) -> GraphRAGState:
        """Step 3: Generate answer using Gemini."""
        logger.info("graph_rag_generate")

        prompt = f"""You are a legal contract analyst. Answer the question based ONLY on the provided context.

CONTEXT:
{state["context_text"]}

QUESTION: {state["query"]}

INSTRUCTIONS:
- Answer based only on the provided context
- If the context doesn't contain the answer, say "I cannot find this information in the provided context"
- Cite source numbers [Source N] when referencing specific information
- Be concise but thorough

ANSWER:"""

        response = await self.gemini_router.generate(
            prompt=prompt,
            complexity=TaskComplexity.SIMPLE,  # Use Flash-Lite for Q&A
            max_tokens=1024
        )

        state["answer"] = response.text
        state["cost"] = response.cost

        # Track cost
        if self.cost_tracker:
            await self.cost_tracker.track_cost(
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost
            )

        return state

    def _extract_sources(self, state: GraphRAGState) -> GraphRAGState:
        """Step 4: Build source attribution list."""
        if not state["retrieval_response"]:
            return state

        state["sources"] = [
            {
                "index": i + 1,
                "type": r.source,
                "contract_id": r.contract_id,
                "score": r.rrf_score,
                "preview": r.content[:100] + "..." if len(r.content) > 100 else r.content
            }
            for i, r in enumerate(state["retrieval_response"].results)
        ]

        return state
```

### Success Criteria
- [x] Full workflow: retrieve -> format -> generate -> sources
- [x] Uses HybridRetriever for retrieval
- [x] Source attribution in responses
- [x] Cost tracking integration
- [x] Graceful error handling

### Implementation Notes
- **Completed:** 2024-01-15
- **File:** `backend/workflows/graph_rag_workflow.py` (338 lines)
- **Tests:** `backend/tests/unit/test_graph_rag_workflow_unit.py` (606 lines, 16 tests)
- **Test Results:** 16/16 tests passing
- Uses TaskComplexity.SIMPLE (Flash-Lite) for cost optimization
- Full workflow: retrieve → format → generate → extract sources
- Graceful error handling with error field in state
- Supports both contract-specific and global search (contract_id=None)
- Cost tracking integration via CostTracker
- Structured logging with structlog
- Source attribution with index, type, score, and preview

---

## Task 4: API Endpoint Integration

**File:** `backend/main.py` (modify existing)

### Changes Required

```python
# Add import
from .workflows.graph_rag_workflow import GraphRAGWorkflow

# Add to startup_event()
graph_rag_workflow = GraphRAGWorkflow(
    vector_store=vector_store,
    graph_store=graph_store,
    cost_tracker=cost_tracker
)
set_graph_rag_workflow(graph_rag_workflow)

# Add new endpoint
@app.post(
    "/api/contracts/graph-query",
    response_model=GraphRAGQueryResponse,
    tags=["Contracts"]
)
async def graph_rag_query(
    request: GraphRAGQueryRequest,
    workflow: GraphRAGWorkflow = Depends(get_graph_rag_workflow)
):
    """
    Query contracts using Graph RAG (hybrid semantic + graph retrieval).

    This endpoint provides enhanced Q&A by combining:
    - Semantic search over document text
    - Graph traversal for related entities (companies, clauses, risks)
    - Re-ranked results using Reciprocal Rank Fusion

    Returns answer with source attribution.
    """
    result = await workflow.run(
        query=request.query,
        contract_id=request.contract_id,
        n_results=request.n_results,
        include_sources=True
    )

    if result["error"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return GraphRAGQueryResponse(
        answer=result["answer"],
        sources=result["sources"],
        semantic_results=result["retrieval_response"].semantic_count,
        graph_results=result["retrieval_response"].graph_count,
        cost=result["cost"]
    )
```

### New Schema Models

**File:** `backend/models/schemas.py` (add)

```python
class GraphRAGQueryRequest(BaseModel):
    """Request for Graph RAG query."""
    query: str = Field(..., min_length=3, description="Question to answer")
    contract_id: Optional[str] = Field(None, description="Specific contract (None = search all)")
    n_results: int = Field(default=5, ge=1, le=20, description="Number of context items")


class GraphRAGSource(BaseModel):
    """Source attribution for Graph RAG response."""
    index: int
    type: str  # "semantic" or "graph"
    contract_id: str
    score: float
    preview: str


class GraphRAGQueryResponse(BaseModel):
    """Response from Graph RAG query."""
    answer: str
    sources: List[GraphRAGSource]
    semantic_results: int
    graph_results: int
    cost: float
```

### Success Criteria
- [x] New `/api/contracts/graph-query` endpoint
- [x] Request/response schemas defined
- [x] Workflow initialization in startup_event
- [x] Error handling with HTTPException
- [x] Integration tests (10 tests, all passing)

### Implementation Notes
- **Completed:** 2024-01-15
- **Files Modified:**
  - `backend/models/schemas.py` - Added GraphRAGQueryRequest, GraphRAGSource, GraphRAGQueryResponse
  - `backend/main.py` - Added graph_rag_workflow initialization and `/api/contracts/graph-query` endpoint
  - `backend/tests/conftest.py` - Added test_client fixture
- **File Created:** `backend/tests/integration/test_graph_rag_integration.py` (290 lines, 10 tests)
- **Test Results:** 10/10 tests passing
- Endpoint validates query length (3-1000 chars), n_results range (1-20)
- Global variable pattern (no dependency injection) for workflow access
- Comprehensive error handling: validation errors (422), service unavailable (503), processing errors (500)
- Request logging with query preview, contract_id, and n_results
- Response logging with result counts and cost

---

## Task 5: Unit Tests

**File:** `backend/tests/unit/test_graph_rag_unit.py`

### Test Cases

```python
"""Unit tests for Graph RAG components."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.graph_context_retriever import GraphContextRetriever, GraphContext
from backend.services.hybrid_retriever import HybridRetriever, RetrievalResult


class TestGraphContextRetriever:
    """Tests for GraphContextRetriever."""

    @pytest.fixture
    def mock_graph_store(self):
        store = MagicMock()
        store.graph = MagicMock()
        return store

    @pytest.fixture
    def retriever(self, mock_graph_store):
        return GraphContextRetriever(mock_graph_store)

    @pytest.mark.asyncio
    async def test_get_context_for_contract_returns_all_entities(self, retriever, mock_graph_store):
        """Should return contract, companies, clauses, and risks."""
        # Arrange
        mock_graph_store.graph.query.return_value = MagicMock(
            result_set=[
                [
                    MagicMock(properties={"contract_id": "c1", "filename": "test.pdf"}),
                    [MagicMock(properties={"name": "Acme", "role": "vendor"})],
                    [MagicMock(properties={"section_name": "Payment", "content": "..."})],
                    [MagicMock(properties={"concern": "Risk", "risk_level": "high"})]
                ]
            ]
        )

        # Act
        result = await retriever.get_context_for_contract("c1")

        # Assert
        assert result.contract_id == "c1"
        assert len(result.companies) == 1
        assert len(result.related_clauses) == 1
        assert len(result.risk_factors) == 1

    @pytest.mark.asyncio
    async def test_get_context_handles_missing_contract(self, retriever, mock_graph_store):
        """Should return empty context for non-existent contract."""
        mock_graph_store.graph.query.return_value = MagicMock(result_set=[])

        result = await retriever.get_context_for_contract("nonexistent")

        assert result is None or result.contract_id is None


class TestHybridRetriever:
    """Tests for HybridRetriever."""

    @pytest.fixture
    def mock_vector_store(self):
        store = AsyncMock()
        store.semantic_search = AsyncMock(return_value=[
            {"id": "1", "text": "Payment terms...", "metadata": {"contract_id": "c1"}, "relevance_score": 0.9},
            {"id": "2", "text": "Termination...", "metadata": {"contract_id": "c1"}, "relevance_score": 0.7}
        ])
        return store

    @pytest.fixture
    def mock_graph_retriever(self):
        retriever = AsyncMock()
        retriever.get_context_for_contract = AsyncMock(return_value=GraphContext(
            contract_id="c1",
            contract_metadata={"risk_level": "medium"},
            companies=[{"name": "Acme", "role": "vendor"}],
            related_clauses=[],
            risk_factors=[{"concern": "Liability", "risk_level": "high"}],
            traversal_depth=1
        ))
        return retriever

    @pytest.fixture
    def retriever(self, mock_vector_store, mock_graph_retriever):
        return HybridRetriever(mock_vector_store, mock_graph_retriever)

    @pytest.mark.asyncio
    async def test_retrieve_combines_semantic_and_graph(self, retriever):
        """Should return results from both semantic and graph sources."""
        result = await retriever.retrieve(query="payment terms", n_semantic=2, n_graph=2)

        assert result.semantic_count == 2
        assert result.graph_count > 0
        assert len(result.results) > 0

    def test_rrf_rerank_orders_by_combined_score(self, retriever):
        """RRF should combine rankings from both sources."""
        results = [
            RetrievalResult(contract_id="c1", content="A", source="semantic", semantic_score=0.9),
            RetrievalResult(contract_id="c1", content="B", source="semantic", semantic_score=0.5),
            RetrievalResult(contract_id="c1", content="C", source="graph", graph_relevance=0.8),
        ]

        ranked = retriever._rrf_rerank(results)

        # A should be first (high semantic score)
        assert ranked[0].content == "A"
        # All should have rrf_score > 0
        assert all(r.rrf_score > 0 for r in ranked)

    def test_rrf_boosts_results_in_both_lists(self, retriever):
        """Results appearing in both semantic and graph should rank higher."""
        results = [
            RetrievalResult(contract_id="c1", content="Both", source="semantic",
                          semantic_score=0.7, graph_relevance=0.7),
            RetrievalResult(contract_id="c1", content="Semantic only", source="semantic",
                          semantic_score=0.9),
        ]

        ranked = retriever._rrf_rerank(results)

        # "Both" should rank higher due to appearing in both lists
        both_result = next(r for r in ranked if r.content == "Both")
        semantic_only = next(r for r in ranked if r.content == "Semantic only")

        assert both_result.rrf_score > semantic_only.rrf_score
```

### Success Criteria
- [ ] Tests for GraphContextRetriever (4+ test cases)
- [ ] Tests for HybridRetriever (4+ test cases)
- [ ] Tests for RRF algorithm correctness
- [ ] All tests pass with mocked dependencies

---

## Task 6: Integration Test

**File:** `backend/tests/integration/test_graph_rag_integration.py`

### Test Cases

```python
"""Integration tests for Graph RAG workflow."""

import pytest
from unittest.mock import patch, AsyncMock


class TestGraphRAGEndpoint:
    """Integration tests for /api/contracts/graph-query endpoint."""

    @pytest.mark.asyncio
    async def test_graph_query_returns_answer_with_sources(self, test_client, mock_services):
        """Should return answer with source attribution."""
        response = test_client.post(
            "/api/contracts/graph-query",
            json={
                "query": "What are the payment terms?",
                "contract_id": "test-contract-123",
                "n_results": 5
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert len(data["sources"]) > 0
        assert data["semantic_results"] >= 0
        assert data["graph_results"] >= 0

    @pytest.mark.asyncio
    async def test_graph_query_global_search(self, test_client, mock_services):
        """Should search across all contracts when contract_id is None."""
        response = test_client.post(
            "/api/contracts/graph-query",
            json={
                "query": "liability clauses",
                "contract_id": None,
                "n_results": 10
            }
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_graph_query_validates_input(self, test_client):
        """Should reject invalid queries."""
        response = test_client.post(
            "/api/contracts/graph-query",
            json={"query": "ab", "n_results": 5}  # Too short
        )

        assert response.status_code == 422
```

### Success Criteria
- [ ] End-to-end test with mocked external services
- [ ] Tests both contract-specific and global search
- [ ] Validates error handling

---

## Implementation Order

1. **Task 1: GraphContextRetriever** (2 hours)
   - Core graph traversal logic
   - No dependencies on other new code

2. **Task 2: HybridRetriever** (2 hours)
   - Depends on Task 1
   - RRF algorithm implementation

3. **Task 5: Unit Tests** (1 hour)
   - Write alongside Tasks 1-2
   - Validates logic before integration

4. **Task 3: GraphRAGWorkflow** (1.5 hours)
   - Depends on Tasks 1-2
   - Orchestrates full flow

5. **Task 4: API Integration** (1 hour)
   - Depends on Task 3
   - Endpoint and schemas

6. **Task 6: Integration Tests** (0.5 hours)
   - Final validation

**Total Estimated Effort:** 8 hours

---

## File Checklist

New files to create:
- [x] `backend/services/graph_context_retriever.py` ✅ Task 1 Complete
- [x] `backend/tests/unit/test_graph_context_retriever_unit.py` ✅ Task 1 Complete
- [x] `backend/services/hybrid_retriever.py` ✅ Task 2 Complete
- [x] `backend/tests/unit/test_hybrid_retriever_unit.py` ✅ Task 2 Complete
- [x] `backend/workflows/graph_rag_workflow.py` ✅ Task 3 Complete
- [x] `backend/tests/unit/test_graph_rag_workflow_unit.py` ✅ Task 3 Complete
- [x] `backend/tests/integration/test_graph_rag_integration.py` ✅ Task 4 Complete

Files to modify:
- [x] `backend/models/schemas.py` (add GraphRAG schemas) ✅ Task 4 Complete
- [x] `backend/main.py` (add endpoint and startup init) ✅ Task 4 Complete
- [x] `backend/tests/conftest.py` (add test_client fixture) ✅ Task 4 Complete

---

## Testing Commands

```bash
# Run unit tests only
pytest backend/tests/unit/test_graph_rag_unit.py -v

# Run integration tests
pytest backend/tests/integration/test_graph_rag_integration.py -v

# Run all Graph RAG tests
pytest backend/tests/ -k "graph_rag" -v

# Test with coverage
pytest backend/tests/ -k "graph_rag" --cov=backend/services --cov=backend/workflows
```
