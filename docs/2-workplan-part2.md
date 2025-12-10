# Part 2: Vector & Graph Storage + LangGraph Workflow

**Parallel Execution Group**: Can run in parallel with Part 1
**Dependencies**: Part 1 services needed for workflow integration
**Estimated Effort**: 3-4 hours

---

## Scope

This part implements the storage layer and agentic workflow:
1. ChromaDB vector store for semantic search
2. Neo4j graph store for contract relationships
3. LangGraph workflow orchestrating the analysis pipeline

---

## Task 2.1: ChromaDB Vector Store

**File**: `backend/services/vector_store.py`

### Requirements
- `ContractVectorStore` class with:
  - Persistent ChromaDB client
  - Collection named "legal_contracts" with cosine similarity
  - Google embedding model integration (`text-embedding-004`)
- Implement methods:
  - `_generate_embeddings()` - batch embedding generation
  - `store_document_sections()` - chunk and store with metadata
  - `semantic_search()` - query with optional doc_id filter
- Chunking strategy: 1000 chars with 200 overlap

### Success Criteria
- [ ] Can store document sections with embeddings
- [ ] Can perform semantic search
- [ ] Returns relevance scores
- [ ] Filters by document ID work

---

## Task 2.2: Neo4j Graph Store

**File**: `backend/services/graph_store.py`

### Requirements
- `ContractGraphStore` class with:
  - Neo4j driver initialization
  - Constraint and index creation on startup
- Node types:
  - `Contract` - central node with metadata
  - `Company` - party nodes
  - `Clause` - section nodes
  - `RiskFactor` - risk concern nodes
- Relationships:
  - `PARTY_TO` - Company → Contract
  - `CONTAINS` - Contract → Clause
  - `HAS_RISK` - Contract → RiskFactor
- Implement methods:
  - `store_contract()` - create full graph structure
  - `get_contract_relationships()` - retrieve all relationships

### Success Criteria
- [ ] Creates proper graph constraints
- [ ] Stores contract with parties, clauses, risks
- [ ] Retrieves full contract graph

---

## Task 2.3: Graph Schemas

**File**: `backend/models/graph_schemas.py`

### Requirements
Define schemas for:
- `ContractNode`
- `CompanyNode`
- `ClauseNode`
- `RiskFactorNode`
- `ContractGraph` (combined response)

### Success Criteria
- [ ] All node schemas defined
- [ ] Proper relationships modeled
- [ ] JSON serialization works

---

## Task 2.4: LangGraph Workflow

**File**: `backend/workflows/contract_analysis_workflow.py`

### Requirements
- Define `ContractAnalysisState` TypedDict with:
  - Input: contract_id, file_bytes, filename, query
  - Intermediate: parsed_document, risk_analysis, key_terms
  - Output: vector_ids, graph_stored, answer, total_cost, errors
- Implement 5 workflow nodes:
  1. `parse_document_node` - LlamaParse integration
  2. `analyze_risk_node` - Gemini Flash for risk analysis
  3. `store_vectors_node` - ChromaDB storage
  4. `store_graph_node` - Neo4j storage
  5. `qa_node` - Gemini Flash-Lite for Q&A
- Build and compile workflow with:
  - Sequential flow: parse → analyze → store_vectors → store_graph → qa → END
  - Entry point at "parse"

### Success Criteria
- [ ] State type validates correctly
- [ ] All nodes execute in sequence
- [ ] Error handling preserves state
- [ ] Cost tracking accumulates across nodes
- [ ] Q&A works with semantic retrieval

---

## Integration Notes

- Vector store uses `backend/services/gemini_router.py` for embeddings (Task 1.1)
- Workflow uses all services from Part 1
- Graph store needs Neo4j running (docker-compose)
- Test with docker-compose services running

---

## Testing Checklist

```bash
# Ensure Docker services are running
docker-compose up -d

# Verify imports
cd backend
python -c "from services.vector_store import ContractVectorStore; print('Vector Store OK')"
python -c "from services.graph_store import ContractGraphStore; print('Graph Store OK')"
python -c "from workflows.contract_analysis_workflow import contract_workflow; print('Workflow OK')"
```

---

## Sample Risk Analysis Prompt

```
Analyze this legal contract for risk factors.

CONTRACT TEXT:
{parsed_text}

Provide analysis in JSON format:
{
    "risk_score": <0-10>,
    "risk_level": "low|medium|high",
    "concerning_clauses": [
        {
            "section": "section name",
            "concern": "description",
            "risk_level": "low|medium|high",
            "recommendation": "suggestion"
        }
    ],
    "key_terms": {
        "payment_amount": "amount",
        "payment_frequency": "frequency",
        "termination_clause": true/false,
        "liability_cap": "amount or unlimited"
    }
}
```
