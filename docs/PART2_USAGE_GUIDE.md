# Part 2 Usage Guide

Quick reference for using the vector store, graph store, and workflow components.

---

## Setup

### 1. Install Dependencies

```bash
pip install google-generativeai neo4j langgraph langchain-google-genai langchain-core chromadb
```

### 2. Start Services

```bash
# Start Neo4j and Redis
docker-compose up -d

# Verify services are running
docker ps
```

### 3. Set Environment Variables

```bash
export GOOGLE_API_KEY=your_google_api_key
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=password123
```

---

## ChromaDB Vector Store

### Basic Usage

```python
from backend.services.vector_store import ContractVectorStore

# Initialize
vector_store = ContractVectorStore(
    persist_directory="./chroma_db",
    collection_name="legal_contracts"
)

# Store document
await vector_store.store_document_sections(
    contract_id="contract_123",
    document_text="Your contract text here...",
    metadata={"filename": "agreement.pdf", "risk_level": "medium"}
)

# Semantic search
results = await vector_store.semantic_search(
    query="What are the payment terms?",
    n_results=5,
    contract_id="contract_123"  # Optional filter
)

for result in results:
    print(f"Relevance: {result['relevance_score']:.2f}")
    print(f"Text: {result['text'][:200]}...")
```

### Advanced Features

```python
# Get collection statistics
stats = vector_store.get_collection_stats()
print(f"Total chunks: {stats['total_chunks']}")

# Delete contract
deleted_count = vector_store.delete_contract("contract_123")
print(f"Deleted {deleted_count} chunks")

# Reset collection (use with caution!)
vector_store.reset_collection()
```

---

## Neo4j Graph Store

### Basic Usage

```python
from backend.services.graph_store import ContractGraphStore
from backend.models.graph_schemas import (
    ContractNode, CompanyNode, ClauseNode, RiskFactorNode
)
from datetime import datetime

# Initialize
graph_store = ContractGraphStore()

# Create nodes
contract = ContractNode(
    contract_id="contract_123",
    filename="agreement.pdf",
    upload_date=datetime.now(),
    risk_score=6.5,
    risk_level="medium"
)

companies = [
    CompanyNode(name="Acme Corp", role="vendor"),
    CompanyNode(name="Client Inc", role="client")
]

clauses = [
    ClauseNode(
        section_name="Payment Terms",
        content="Payment within 30 days",
        clause_type="payment",
        importance="high"
    )
]

risk_factors = [
    RiskFactorNode(
        concern="Unlimited liability exposure",
        risk_level="high",
        section="Liability",
        recommendation="Negotiate a cap"
    )
]

# Store complete graph
graph = await graph_store.store_contract(
    contract=contract,
    companies=companies,
    clauses=clauses,
    risk_factors=risk_factors
)

# Retrieve graph
retrieved = await graph_store.get_contract_relationships("contract_123")
print(f"Contract: {retrieved.contract.filename}")
print(f"Companies: {len(retrieved.companies)}")
print(f"Clauses: {len(retrieved.clauses)}")
print(f"Risks: {len(retrieved.risk_factors)}")
```

### Advanced Queries

```python
# Find similar contracts
similar = await graph_store.find_similar_contracts(
    risk_level="high",
    limit=5
)

for contract in similar:
    print(f"{contract.filename} - Risk: {contract.risk_score}")

# Delete contract
deleted = graph_store.delete_contract("contract_123")
print(f"Deleted: {deleted}")

# Close connection
graph_store.close()
```

---

## LangGraph Workflow

### Full Pipeline

```python
from backend.workflows.contract_analysis_workflow import get_workflow

# Initialize workflow (with services)
workflow = get_workflow(initialize_stores=True)

# Read PDF file
with open("contract.pdf", "rb") as f:
    file_bytes = f.read()

# Run complete analysis
result = await workflow.run(
    contract_id="contract_123",
    file_bytes=file_bytes,
    filename="service_agreement.pdf",
    query="What are the termination conditions?"
)

# Check results
print(f"Parsed: {len(result.get('parsed_document', ''))} chars")
print(f"Risk Score: {result.get('risk_analysis', {}).get('risk_score')}")
print(f"Risk Level: {result.get('risk_analysis', {}).get('risk_level')}")
print(f"Vector IDs: {len(result.get('vector_ids', []))} chunks stored")
print(f"Graph Stored: {result.get('graph_stored')}")
print(f"Answer: {result.get('answer')}")
print(f"Total Cost: ${result.get('total_cost', 0):.4f}")

# Check for errors
if result.get('errors'):
    print(f"Errors: {result['errors']}")
```

### Testing Without Services

```python
# For testing/development without Neo4j running
workflow = get_workflow(initialize_stores=False)

# Workflow will use mock data for testing
result = await workflow.run(
    contract_id="test_123",
    file_bytes=b"test content",
    filename="test.pdf"
)
```

---

## Graph Schemas

### Creating Nodes

```python
from backend.models.graph_schemas import (
    ContractNode, CompanyNode, ClauseNode,
    RiskFactorNode, ContractGraph
)
from datetime import datetime

# Contract
contract = ContractNode(
    contract_id="contract_123",
    filename="agreement.pdf",
    upload_date=datetime.now(),
    risk_score=5.0,
    risk_level="medium",
    payment_amount="$50,000",
    payment_frequency="monthly",
    has_termination_clause=True,
    liability_cap="$100,000"
)

# Company
company = CompanyNode(
    name="Tech Corp",
    role="service_provider",
    company_id="tech_corp_001"
)

# Clause
clause = ClauseNode(
    section_name="Confidentiality",
    content="All information shall remain confidential...",
    clause_type="confidentiality",
    importance="high"
)

# Risk Factor
risk = RiskFactorNode(
    concern="No liability cap specified",
    risk_level="high",
    section="Liability Clause",
    recommendation="Add a specific liability cap amount"
)

# Complete Graph
graph = ContractGraph(
    contract=contract,
    companies=[company],
    clauses=[clause],
    risk_factors=[risk]
)

# Serialize to JSON
json_str = graph.model_dump_json(indent=2)
print(json_str)

# Deserialize from JSON
loaded = ContractGraph.model_validate_json(json_str)
```

---

## Common Patterns

### 1. Store and Query Pattern

```python
# Store contract
vector_ids = await vector_store.store_document_sections(
    contract_id="contract_123",
    document_text=parsed_text,
    metadata={"risk_level": "medium"}
)

await graph_store.store_contract(
    contract=contract,
    companies=companies,
    clauses=clauses,
    risk_factors=risks
)

# Later: Query
search_results = await vector_store.semantic_search(
    query="payment terms",
    contract_id="contract_123"
)

graph_data = await graph_store.get_contract_relationships("contract_123")
```

### 2. Batch Processing

```python
contracts = [...]  # List of contracts

for contract_file in contracts:
    try:
        result = await workflow.run(
            contract_id=f"contract_{i}",
            file_bytes=contract_file.read(),
            filename=contract_file.name
        )

        print(f"Processed {contract_file.name}: {result.get('risk_level')}")

    except Exception as e:
        print(f"Error processing {contract_file.name}: {e}")
```

### 3. Q&A Session

```python
# First, analyze and store contract
result = await workflow.run(
    contract_id="contract_123",
    file_bytes=file_bytes,
    filename="agreement.pdf"
)

# Then ask multiple questions
questions = [
    "What are the payment terms?",
    "Is there a termination clause?",
    "What are the key risks?"
]

for question in questions:
    result = await workflow.run(
        contract_id="contract_123",
        file_bytes=file_bytes,
        filename="agreement.pdf",
        query=question
    )

    print(f"Q: {question}")
    print(f"A: {result.get('answer')}\n")
```

---

## Error Handling

### Robust Error Handling

```python
from neo4j.exceptions import ServiceUnavailable

try:
    # Initialize stores
    vector_store = ContractVectorStore()
    graph_store = ContractGraphStore()

    # Run workflow
    result = await workflow.run(...)

    # Check for errors
    if result.get('errors'):
        print(f"Workflow errors: {result['errors']}")

except ServiceUnavailable:
    print("Neo4j is not running. Start with: docker-compose up -d")

except ValueError as e:
    if "GOOGLE_API_KEY" in str(e):
        print("Set GOOGLE_API_KEY environment variable")
    else:
        raise

except Exception as e:
    print(f"Unexpected error: {e}")
    import traceback
    traceback.print_exc()
```

---

## Configuration

### Custom Vector Store

```python
vector_store = ContractVectorStore(
    persist_directory="/custom/path/chroma",
    collection_name="my_legal_docs"
)
```

### Custom Graph Store

```python
graph_store = ContractGraphStore(
    uri="bolt://remote-server:7687",
    username="custom_user",
    password="custom_password"
)
```

---

## Performance Tips

### Vector Store
- Batch operations when possible
- Use contract_id filter to narrow search
- Keep chunks reasonable size (1000 chars)
- Monitor embedding API costs

### Graph Store
- Use indexes for frequently queried fields
- MERGE instead of CREATE for idempotency
- Close connections when done
- Use transactions for multiple operations

### Workflow
- Initialize stores once and reuse
- Monitor total_cost in results
- Use query parameter only when needed
- Cache parsed documents if re-analyzing

---

## Debugging

### Enable Logging

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Inspect State

```python
result = await workflow.run(...)

# Check intermediate state
print(f"Parsed: {result.get('parsed_document')[:500]}")
print(f"Risk Analysis: {result.get('risk_analysis')}")
print(f"Key Terms: {result.get('key_terms')}")
print(f"Vector IDs: {result.get('vector_ids')}")
```

### Verify Services

```bash
# Check Neo4j
docker exec -it ps-demo-neo4j-1 cypher-shell -u neo4j -p password123

# In cypher-shell:
MATCH (n) RETURN count(n);

# Check ChromaDB
python3 -c "from backend.services.vector_store import ContractVectorStore; vs = ContractVectorStore(); print(vs.get_collection_stats())"
```

---

## Testing

Run the test suite:

```bash
python3 backend/test_part2.py
```

Expected output:
```
✅ PASS: Graph Schemas
✅ PASS: Vector Store
✅ PASS: Graph Store
✅ PASS: Workflow

Total: 4/4 tests passed
```

---

## Troubleshooting

### "GOOGLE_API_KEY environment variable not set"
```bash
export GOOGLE_API_KEY=your_key
```

### "Couldn't connect to localhost:7687"
```bash
docker-compose up -d neo4j
```

### "Collection already exists"
```python
# Reset collection
vector_store.reset_collection()
```

### "Module not found: backend"
```bash
# Run from project root
cd /path/to/ps-demo
python3 your_script.py
```

---

## Next Steps

1. Review the [Completion Report](PART2_COMPLETION_REPORT.md)
2. Check the [Workplan](2-workplan-part2.md) for context
3. Wait for Part 1 completion for full integration
4. Run integration tests once Part 1 is ready

---

*Guide updated: December 10, 2024*
