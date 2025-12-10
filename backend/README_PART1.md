# Part 1: Infrastructure & Core Services

Quick reference guide for the foundational services.

## Quick Start

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Set environment variables
export GOOGLE_API_KEY="your_key"
export LLAMA_CLOUD_API_KEY="your_key"
export REDIS_URL="redis://localhost:6379"

# Run tests
python3 test_part1.py
```

## Services Overview

### 1. Gemini Router (`services/gemini_router.py`)

Routes requests to appropriate Gemini model based on complexity:

```python
from services import GeminiRouter, TaskComplexity

router = GeminiRouter(api_key=GOOGLE_API_KEY)

# Choose complexity based on task
result = await router.generate(
    prompt="Your prompt here",
    complexity=TaskComplexity.SIMPLE,  # SIMPLE, BALANCED, COMPLEX, REASONING
)

print(f"Model: {result.model_name}")
print(f"Cost: ${result.cost:.6f}")
```

**Models**:
- `SIMPLE` → gemini-2.5-flash-lite ($0.075/$0.30 per 1M)
- `BALANCED` → gemini-2.5-flash ($0.15/$0.60 per 1M)
- `COMPLEX` → gemini-2.5-pro ($1.25/$5.00 per 1M)
- `REASONING` → gemini-3-pro ($2.50/$10.00 per 1M) + thinking

### 2. Cost Tracker (`services/cost_tracker.py`)

Redis-based cost tracking with 30-day retention:

```python
from services import CostTracker

tracker = CostTracker(redis_url=REDIS_URL)

# Track API call
tracker.track_api_call(
    model_name=result.model_name,
    input_tokens=result.input_tokens,
    output_tokens=result.output_tokens,
    thinking_tokens=result.thinking_tokens,
    cost=result.cost,
    operation_type="query",  # parse, analyze, query, etc.
)

# Get daily summary
daily = tracker.get_daily_costs()
print(f"Today: ${daily['total_cost']:.4f}")
print(f"Calls: {daily['total_calls']}")
print(f"By model: {daily['by_model']}")
```

### 3. LlamaParse Service (`services/llamaparse_service.py`)

Legal document parsing optimized for contracts:

```python
from services import LegalDocumentParser

parser = LegalDocumentParser(api_key=LLAMA_CLOUD_API_KEY)

with open("contract.pdf", "rb") as f:
    pdf_bytes = f.read()

result = await parser.parse_document(pdf_bytes, "contract.pdf")

# Extracted data
print(result['parsed_text'])       # Full markdown
print(result['sections'])          # Numbered sections
print(result['tables'])            # Tables as markdown
print(result['metadata'])          # Parties, dates, type, jurisdiction
```

### 4. Pydantic Schemas (`models/schemas.py`)

Data models for API:

```python
from models import (
    ContractUploadResponse,
    RiskAnalysis,
    KeyTerms,
    ContractQuery,
    QueryResponse,
    CostAnalytics,
)

# Create and validate
query = ContractQuery(
    contract_id="contract-123",
    question="What are the termination conditions?",
)

# Serialize to JSON
json_data = query.model_dump_json()
```

## Common Patterns

### Pattern 1: Parse + Analyze + Track

```python
# Initialize services
router = GeminiRouter(api_key=GOOGLE_API_KEY)
parser = LegalDocumentParser(api_key=LLAMA_CLOUD_API_KEY)
tracker = CostTracker(redis_url=REDIS_URL)

# Parse document
parsed = await parser.parse_document(pdf_bytes, filename)

# Analyze with Gemini
prompt = f"Analyze risks in this contract:\n\n{parsed['parsed_text'][:5000]}"
result = await router.generate(prompt, TaskComplexity.COMPLEX)

# Track cost
tracker.track_api_call(
    model_name=result.model_name,
    input_tokens=result.input_tokens,
    output_tokens=result.output_tokens,
    thinking_tokens=result.thinking_tokens,
    cost=result.cost,
    operation_type="analyze",
)
```

### Pattern 2: Multi-step with Cost Optimization

```python
# Start with simple model
simple_result = await router.generate(
    "Extract party names from this contract: ...",
    TaskComplexity.SIMPLE,
)

# Use complex model only when needed
if needs_deep_analysis:
    complex_result = await router.generate(
        "Provide detailed risk analysis...",
        TaskComplexity.COMPLEX,
    )
```

### Pattern 3: Cost Analytics

```python
from datetime import datetime, timedelta

# Daily costs
today = tracker.get_daily_costs()

# Last 7 days
week_ago = datetime.utcnow() - timedelta(days=7)
week_costs = tracker.get_total_costs(start_date=week_ago)

print(f"7-day total: ${week_costs['total_cost']:.2f}")
print(f"Average per day: ${week_costs['total_cost'] / 7:.2f}")
```

## Task Complexity Guide

Choose the right model for your task:

| Task Type | Complexity | Model | Use Case |
|-----------|------------|-------|----------|
| Extract dates, parties | SIMPLE | flash-lite | Quick extraction |
| Standard Q&A | BALANCED | flash | Most queries |
| Risk analysis | COMPLEX | pro | Deep analysis |
| Multi-step reasoning | REASONING | 3-pro | Complex legal reasoning |

## Error Handling

All services include comprehensive error handling:

```python
from redis.exceptions import RedisError

try:
    tracker.track_api_call(...)
except RedisError as e:
    logger.error(f"Redis error: {e}")
    # Handle gracefully - maybe queue for retry

try:
    result = await router.generate(...)
except Exception as e:
    logger.error(f"Generation failed: {e}")
    # Maybe fall back to simpler model
```

## Testing

```bash
# Run integration tests
python3 test_part1.py

# Test individual components
python3 -c "from services import GeminiRouter; print('OK')"
python3 -c "from services import CostTracker; print('OK')"
python3 -c "from models import ContractUploadResponse; print('OK')"
```

## Dependencies

```
google-generativeai>=1.33.0  # Gemini Router
redis                         # Cost Tracker
llama-parse==0.6.88          # LlamaParse Service
pydantic>=2.0                # Schemas
```

## Next Steps

These services are used by:
- **Part 2**: LangGraph agents and workflows
- **Part 3**: FastAPI endpoints
- **Part 4**: Next.js frontend (via API)

See `docs/PART1-IMPLEMENTATION-SUMMARY.md` for detailed documentation.
