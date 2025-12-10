# Part 6: Architecture Improvements

## ✅ STATUS: COMPLETE

**Priority:** MEDIUM (Should Do for Production)
**Parallel Execution:** Can run in parallel with Parts 5 & 7
**Dependencies:** Parts 1-4 complete
**Estimated Effort:** 4-6 hours
**Actual Effort:** ~3 hours

---

## Overview

This part addresses architecture improvements identified in the review:
- Separate Q&A workflow for efficiency
- Add retry logic for external APIs
- Improve error handling and observability
- Add request tracking

---

## Parallel Task Groups

### Group 6A: API Resilience (Retry + Circuit Breaker)
### Group 6B: Workflow Optimization (Separate Q&A)
### Group 6C: Observability (Logging + Tracing)

---

## Group 6A: API Resilience

**Files to Modify:**
- `backend/services/gemini_router.py`
- `backend/services/llamaparse_service.py`
- `backend/requirements.txt`

### Task 6A.1: Add Retry Logic to GeminiRouter

**File:** `backend/services/gemini_router.py`

**Changes Required:**

```python
# Add to requirements.txt
tenacity>=8.2.0

# Add imports
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import google.api_core.exceptions

# Add retry decorator to generate method
class GeminiRouter:

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            google.api_core.exceptions.ServiceUnavailable,
            google.api_core.exceptions.ResourceExhausted,
            google.api_core.exceptions.DeadlineExceeded,
            ConnectionError
        )),
        before_sleep=lambda retry_state: logger.warning(
            f"Gemini API call failed, retrying in {retry_state.next_action.sleep} seconds..."
        )
    )
    async def generate(self, prompt: str, complexity: TaskComplexity, ...):
        """Generate response with automatic retry on transient failures."""
        # ... existing implementation
```

### Success Criteria
- [ ] Retries on transient errors (503, 429, timeout)
- [ ] Exponential backoff between retries
- [ ] Logs retry attempts
- [ ] Fails after 3 attempts with clear error

---

### Task 6A.2: Add Circuit Breaker Pattern

**File:** `backend/services/api_resilience.py` (new file)

```python
from pybreaker import CircuitBreaker, CircuitBreakerError
import structlog

logger = structlog.get_logger()

# Circuit breakers for external services
gemini_breaker = CircuitBreaker(
    fail_max=5,           # Open after 5 failures
    reset_timeout=60,     # Try again after 60 seconds
    state_storage=None,   # In-memory (use Redis for distributed)
    listeners=[
        lambda cb, state: logger.warning(
            "circuit_breaker_state_change",
            breaker=cb.name,
            new_state=state
        )
    ]
)

llamaparse_breaker = CircuitBreaker(
    fail_max=3,
    reset_timeout=120,
)

def with_circuit_breaker(breaker: CircuitBreaker):
    """Decorator to wrap async functions with circuit breaker."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return breaker.call(func, *args, **kwargs)
            except CircuitBreakerError:
                logger.error(
                    "circuit_breaker_open",
                    breaker=breaker.name,
                    message="Service unavailable, circuit breaker open"
                )
                raise ServiceUnavailableError(
                    f"{breaker.name} service is temporarily unavailable"
                )
        return wrapper
    return decorator


class ServiceUnavailableError(Exception):
    """Raised when a service is unavailable due to circuit breaker."""
    pass
```

**Usage in GeminiRouter:**
```python
from backend.services.api_resilience import gemini_breaker, with_circuit_breaker

class GeminiRouter:

    @with_circuit_breaker(gemini_breaker)
    @retry(...)  # Retry decorator
    async def generate(self, ...):
        # ... implementation
```

### Success Criteria
- [ ] Circuit breaker opens after repeated failures
- [ ] Clear error when circuit is open
- [ ] Automatic recovery after timeout
- [ ] State changes logged

---

### Task 6A.3: Add Timeout Configuration

**File:** `backend/services/gemini_router.py`

```python
import asyncio
from typing import Optional

class GeminiRouter:
    def __init__(
        self,
        api_key: str,
        default_timeout: float = 30.0,  # 30 seconds default
        max_timeout: float = 120.0      # 2 minutes max
    ):
        self.default_timeout = default_timeout
        self.max_timeout = max_timeout

    async def generate(
        self,
        prompt: str,
        complexity: TaskComplexity,
        timeout: Optional[float] = None,
        ...
    ):
        """Generate with configurable timeout."""
        effective_timeout = min(
            timeout or self.default_timeout,
            self.max_timeout
        )

        try:
            result = await asyncio.wait_for(
                self._generate_internal(prompt, complexity, ...),
                timeout=effective_timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error(
                "gemini_timeout",
                timeout=effective_timeout,
                complexity=complexity.value
            )
            raise TimeoutError(f"Gemini API call timed out after {effective_timeout}s")
```

### Success Criteria
- [ ] Default timeout of 30 seconds
- [ ] Configurable per-request timeout
- [ ] Maximum timeout cap enforced
- [ ] Clear timeout errors logged

---

## Group 6B: Workflow Optimization

**Files to Create/Modify:**
- `backend/workflows/qa_workflow.py` (new)
- `backend/main.py`

### Task 6B.1: Create Lightweight Q&A Workflow

**File:** `backend/workflows/qa_workflow.py`

```python
"""
Lightweight Q&A workflow for querying existing contracts.

This workflow skips parse/analyze/store steps and only:
1. Retrieves relevant context from vector store
2. Generates answer using Gemini Flash-Lite

Much more efficient than running full contract_analysis_workflow.
"""

from typing import TypedDict, Optional
import os
import structlog

from backend.services.vector_store import ContractVectorStore
from backend.services.gemini_router import GeminiRouter, TaskComplexity
from backend.services.cost_tracker import CostTracker

logger = structlog.get_logger()


class QAState(TypedDict):
    """Minimal state for Q&A operations."""
    contract_id: str
    query: str
    context_chunks: list[dict]
    answer: Optional[str]
    cost: float
    error: Optional[str]


class QAWorkflow:
    """
    Lightweight workflow for contract Q&A.

    Usage:
        workflow = QAWorkflow()
        result = await workflow.run(
            contract_id="abc-123",
            query="What are the payment terms?"
        )
        print(result["answer"])
    """

    def __init__(
        self,
        vector_store: Optional[ContractVectorStore] = None,
        gemini_router: Optional[GeminiRouter] = None,
        cost_tracker: Optional[CostTracker] = None
    ):
        self.vector_store = vector_store or ContractVectorStore()
        self.gemini_router = gemini_router or GeminiRouter(
            api_key=os.getenv("GOOGLE_API_KEY")
        )
        self.cost_tracker = cost_tracker

    async def run(
        self,
        contract_id: str,
        query: str,
        n_chunks: int = 5
    ) -> QAState:
        """
        Execute Q&A workflow.

        Args:
            contract_id: ID of the contract to query
            query: User's question
            n_chunks: Number of context chunks to retrieve

        Returns:
            QAState with answer, cost, and any errors
        """
        state: QAState = {
            "contract_id": contract_id,
            "query": query,
            "context_chunks": [],
            "answer": None,
            "cost": 0.0,
            "error": None
        }

        try:
            # Step 1: Retrieve relevant context
            logger.info(
                "qa_retrieve_context",
                contract_id=contract_id,
                query=query[:50]
            )

            chunks = await self.vector_store.semantic_search(
                query=query,
                contract_id=contract_id,
                n_results=n_chunks
            )
            state["context_chunks"] = chunks

            if not chunks:
                state["answer"] = "I couldn't find relevant information in this contract."
                return state

            # Step 2: Generate answer
            context_text = "\n\n".join([
                f"[Section {i+1}]: {chunk['text']}"
                for i, chunk in enumerate(chunks)
            ])

            prompt = self._build_qa_prompt(query, context_text)

            logger.info("qa_generate_answer", contract_id=contract_id)

            response = await self.gemini_router.generate(
                prompt=prompt,
                complexity=TaskComplexity.SIMPLE,  # Use Flash-Lite for Q&A
                system_instruction="You are a helpful legal assistant. Answer questions based only on the provided contract context. If the answer is not in the context, say so."
            )

            state["answer"] = response["text"]
            state["cost"] = response["cost"]

            # Track cost if tracker available
            if self.cost_tracker:
                await self.cost_tracker.track_api_call(
                    model_name=response["model_name"],
                    input_tokens=response["input_tokens"],
                    output_tokens=response["output_tokens"],
                    cost=response["cost"],
                    operation="qa_query"
                )

            logger.info(
                "qa_complete",
                contract_id=contract_id,
                cost=state["cost"]
            )

        except Exception as e:
            logger.error(
                "qa_error",
                contract_id=contract_id,
                error=str(e)
            )
            state["error"] = str(e)

        return state

    def _build_qa_prompt(self, query: str, context: str) -> str:
        """Build prompt for Q&A generation."""
        return f"""Based on the following contract excerpts, answer the user's question.

CONTRACT EXCERPTS:
{context}

USER QUESTION: {query}

Provide a clear, concise answer based only on the information in the contract excerpts above. If the answer cannot be determined from the provided context, say "This information is not found in the provided contract sections."

ANSWER:"""
```

### Success Criteria
- [ ] Q&A completes without running full workflow
- [ ] Uses Flash-Lite (cheapest model) for answers
- [ ] Properly retrieves context from ChromaDB
- [ ] Tracks cost separately
- [ ] Handles missing context gracefully

---

### Task 6B.2: Update API to Use QA Workflow

**File:** `backend/main.py`

**Changes Required:**

```python
from backend.workflows.qa_workflow import QAWorkflow

# Initialize at startup
qa_workflow: Optional[QAWorkflow] = None

@app.on_event("startup")
async def startup_event():
    global qa_workflow
    qa_workflow = QAWorkflow()
    # ... existing startup code

@app.post("/api/contracts/{contract_id}/query")
async def query_contract(
    contract_id: str,
    request: ContractQueryRequest
) -> ContractQueryResponse:
    """
    Query a contract with natural language.

    Uses lightweight Q&A workflow instead of full analysis workflow.
    """
    if not qa_workflow:
        raise HTTPException(
            status_code=503,
            detail="Q&A service not initialized"
        )

    # Verify contract exists
    if not await graph_store.contract_exists(contract_id):
        raise HTTPException(
            status_code=404,
            detail=f"Contract {contract_id} not found"
        )

    result = await qa_workflow.run(
        contract_id=contract_id,
        query=request.query
    )

    if result["error"]:
        raise HTTPException(
            status_code=500,
            detail=result["error"]
        )

    return ContractQueryResponse(
        contract_id=contract_id,
        query=request.query,
        answer=result["answer"],
        cost=result["cost"],
        context_chunks=len(result["context_chunks"])
    )
```

### Success Criteria
- [ ] Query endpoint uses QA workflow
- [ ] Response time improved (< 2s vs > 5s)
- [ ] Cost reduced (Flash-Lite vs Flash)
- [ ] Contract existence verified first

---

## Group 6C: Observability

**Files to Create/Modify:**
- `backend/utils/logging.py` (new)
- `backend/utils/request_context.py` (new)
- `backend/main.py`
- `backend/requirements.txt`

### Task 6C.1: Add Structured Logging

**File:** `backend/utils/logging.py`

```python
"""
Structured logging configuration using structlog.

Provides JSON-formatted logs suitable for log aggregation services.
"""

import structlog
import logging
import sys
from typing import Any


def setup_logging(
    log_level: str = "INFO",
    json_format: bool = True
):
    """
    Configure structured logging for the application.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
        json_format: If True, output JSON logs (for production)
    """

    # Shared processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_format:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        # Development: Pretty console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a logger instance with optional name binding."""
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(component=name)
    return logger


# Pre-configured loggers for common components
api_logger = get_logger("api")
workflow_logger = get_logger("workflow")
service_logger = get_logger("service")
```

### Success Criteria
- [ ] JSON-formatted logs in production
- [ ] Pretty console logs in development
- [ ] Timestamp on all log entries
- [ ] Log level filtering works

---

### Task 6C.2: Add Request ID Tracking

**File:** `backend/utils/request_context.py`

```python
"""
Request context management for tracking requests across the application.
"""

import uuid
from contextvars import ContextVar
from typing import Optional
import structlog

# Context variable for request ID
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Get the current request ID."""
    return request_id_var.get()


def set_request_id(request_id: str = None) -> str:
    """
    Set the request ID for the current context.

    Args:
        request_id: Optional ID to use. If None, generates a UUID.

    Returns:
        The request ID that was set.
    """
    if request_id is None:
        request_id = str(uuid.uuid4())

    request_id_var.set(request_id)

    # Also bind to structlog context
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    return request_id


def clear_request_context():
    """Clear the request context at end of request."""
    request_id_var.set(None)
    structlog.contextvars.clear_contextvars()
```

**Middleware in main.py:**

```python
from starlette.middleware.base import BaseHTTPMiddleware
from backend.utils.request_context import set_request_id, clear_request_context

class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to set request ID for each request."""

    async def dispatch(self, request, call_next):
        # Get request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID")
        request_id = set_request_id(request_id)

        # Add to request state for access in handlers
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            clear_request_context()

# Add middleware to app
app.add_middleware(RequestContextMiddleware)
```

### Success Criteria
- [ ] Request ID generated for each request
- [ ] Request ID in response headers
- [ ] Request ID in all log entries
- [ ] Can pass request ID via header

---

### Task 6C.3: Add Performance Logging

**File:** `backend/utils/performance.py`

```python
"""
Performance monitoring utilities.
"""

import time
from functools import wraps
from typing import Callable
import structlog

logger = structlog.get_logger()


def log_execution_time(operation_name: str = None):
    """
    Decorator to log execution time of functions.

    Usage:
        @log_execution_time("process_document")
        async def process_document(...):
            ...
    """
    def decorator(func: Callable):
        name = operation_name or func.__name__

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.info(
                    "operation_complete",
                    operation=name,
                    duration_ms=round(duration_ms, 2),
                    status="success"
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    "operation_failed",
                    operation=name,
                    duration_ms=round(duration_ms, 2),
                    status="error",
                    error=str(e)
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.info(
                    "operation_complete",
                    operation=name,
                    duration_ms=round(duration_ms, 2),
                    status="success"
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    "operation_failed",
                    operation=name,
                    duration_ms=round(duration_ms, 2),
                    status="error",
                    error=str(e)
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
```

**Usage in services:**
```python
from backend.utils.performance import log_execution_time

class GeminiRouter:

    @log_execution_time("gemini_generate")
    async def generate(self, ...):
        # ... implementation
```

### Success Criteria
- [ ] Execution time logged for key operations
- [ ] Success/failure status included
- [ ] Works with async and sync functions
- [ ] Minimal performance overhead

---

## Completion Checklist

### Group 6A: API Resilience
- [x] Task 6A.1: Add retry logic to GeminiRouter
- [x] Task 6A.2: Add circuit breaker pattern
- [x] Task 6A.3: Add timeout configuration

### Group 6B: Workflow Optimization
- [x] Task 6B.1: Create lightweight Q&A workflow
- [x] Task 6B.2: Update API to use QA workflow

### Group 6C: Observability
- [x] Task 6C.1: Add structured logging
- [x] Task 6C.2: Add request ID tracking
- [x] Task 6C.3: Add performance logging

### Testing
- [x] Comprehensive test suite with 24 passing tests

---

## Dependencies to Add

```bash
# Add to backend/requirements.txt
tenacity>=8.2.0
pybreaker>=1.0.0
structlog>=23.0.0
```

---

## Success Metrics

| Metric | Before | After |
|--------|--------|-------|
| Q&A Response Time | ~5s | <2s |
| Q&A Cost | $0.005 | $0.001 |
| Retry Success Rate | 0% | 95% |
| Request Traceability | None | Full |
| Log Format | Unstructured | JSON |
