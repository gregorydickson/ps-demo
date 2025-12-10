# Part 5: Testing Strategy Implementation

## 🔴 STATUS: NOT STARTED

**Priority:** HIGH (Must Do for Demo)
**Parallel Execution:** Can run in parallel with Parts 6 & 7
**Dependencies:** Parts 1-4 complete
**Estimated Effort:** 4-6 hours

---

## Overview

This part addresses the critical testing gaps identified in the architecture review:
- Current test coverage: ~30% (mostly structural validation)
- Target test coverage: ~70% (functional + integration)
- Focus: Pragmatic tests that catch real bugs, not 100% coverage

---

## Parallel Task Groups

### Group 5A: Backend Unit Tests (Can run independently)
### Group 5B: Backend Integration Tests (Can run independently)
### Group 5C: Frontend Tests (Can run independently)

---

## Group 5A: Backend Unit Tests

**Files to Create:**
- `backend/tests/unit/test_gemini_router_unit.py`
- `backend/tests/unit/test_cost_tracker_unit.py`
- `backend/tests/unit/test_vector_store_unit.py`
- `backend/tests/conftest.py`

### Task 5A.1: Test Fixtures Setup

**File:** `backend/tests/conftest.py`

```python
import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def mock_redis():
    """Mock Redis client for cost tracker tests."""
    redis = MagicMock()
    redis.hset = MagicMock()
    redis.hgetall = MagicMock(return_value={})
    redis.expire = MagicMock()
    return redis

@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    response = MagicMock()
    response.text = "Test response"
    response.usage_metadata.prompt_token_count = 100
    response.usage_metadata.candidates_token_count = 50
    response.usage_metadata.total_token_count = 150
    return response

@pytest.fixture
def sample_contract_text():
    """Sample contract text for testing."""
    return """
    SERVICE AGREEMENT

    This Agreement is entered into between:
    Party A: Acme Corporation ("Client")
    Party B: TechServ Inc. ("Provider")

    Effective Date: January 1, 2025

    1. PAYMENT TERMS
    Payment shall be made within Net 30 days.

    2. LIABILITY
    Total liability shall not exceed $1,000,000.

    3. TERMINATION
    Either party may terminate with 30 days notice.
    """
```

### Success Criteria
- [ ] conftest.py provides reusable fixtures
- [ ] Mocks isolate external dependencies
- [ ] Fixtures are well-documented

---

### Task 5A.2: GeminiRouter Unit Tests

**File:** `backend/tests/unit/test_gemini_router_unit.py`

**Test Cases:**
```python
import pytest
from backend.services.gemini_router import GeminiRouter, TaskComplexity

class TestGeminiRouterUnit:

    def test_cost_calculation_simple(self):
        """Test cost calculation for SIMPLE tasks."""
        router = GeminiRouter(api_key="test")
        # Flash-Lite: $0.04/M input, $0.12/M output
        cost = router._calculate_cost(
            complexity=TaskComplexity.SIMPLE,
            input_tokens=1000,
            output_tokens=500
        )
        expected = (1000 * 0.04 / 1_000_000) + (500 * 0.12 / 1_000_000)
        assert abs(cost - expected) < 0.0001

    def test_cost_calculation_balanced(self):
        """Test cost calculation for BALANCED tasks."""
        router = GeminiRouter(api_key="test")
        # Flash: $0.075/M input, $0.30/M output
        cost = router._calculate_cost(
            complexity=TaskComplexity.BALANCED,
            input_tokens=1000,
            output_tokens=500
        )
        expected = (1000 * 0.075 / 1_000_000) + (500 * 0.30 / 1_000_000)
        assert abs(cost - expected) < 0.0001

    def test_model_selection_by_complexity(self):
        """Test correct model is selected for each complexity level."""
        router = GeminiRouter(api_key="test")

        assert "flash-lite" in router.get_model_name(TaskComplexity.SIMPLE).lower()
        assert "flash" in router.get_model_name(TaskComplexity.BALANCED).lower()
        assert "pro" in router.get_model_name(TaskComplexity.COMPLEX).lower()

    def test_thinking_budget_only_for_reasoning(self):
        """Test that thinking budget is only valid for REASONING complexity."""
        router = GeminiRouter(api_key="test")

        # Should not raise for REASONING
        config = router.get_config(TaskComplexity.REASONING, thinking_budget=1000)
        assert config.thinking_budget == 1000

        # Should ignore or raise for non-REASONING
        config = router.get_config(TaskComplexity.SIMPLE, thinking_budget=1000)
        assert config.thinking_budget == 0 or config.thinking_budget is None
```

### Success Criteria
- [ ] Cost calculations verified for all complexity levels
- [ ] Model selection logic tested
- [ ] Thinking budget validation works
- [ ] Edge cases (0 tokens, max tokens) handled

---

### Task 5A.3: CostTracker Unit Tests

**File:** `backend/tests/unit/test_cost_tracker_unit.py`

**Test Cases:**
```python
import pytest
from unittest.mock import MagicMock
from backend.services.cost_tracker import CostTracker

class TestCostTrackerUnit:

    def test_track_api_call_stores_data(self, mock_redis):
        """Test that API call data is stored in Redis."""
        tracker = CostTracker(redis_client=mock_redis)

        tracker.track_api_call(
            model_name="gemini-2.5-flash",
            input_tokens=100,
            output_tokens=50,
            cost=0.001,
            operation="risk_analysis"
        )

        # Verify Redis hset was called
        assert mock_redis.hset.called

    def test_get_daily_costs_aggregates_correctly(self, mock_redis):
        """Test daily cost aggregation."""
        # Setup mock data
        mock_redis.hgetall.return_value = {
            "gemini-2.5-flash:total_cost": "0.005",
            "gemini-2.5-flash:total_tokens": "1000",
            "gemini-2.5-flash:call_count": "5"
        }

        tracker = CostTracker(redis_client=mock_redis)
        result = tracker.get_daily_costs()

        assert result["total_cost"] == 0.005
        assert result["total_tokens"] == 1000

    def test_handles_redis_unavailable(self):
        """Test graceful handling when Redis is unavailable."""
        mock_redis = MagicMock()
        mock_redis.hset.side_effect = Exception("Connection refused")

        tracker = CostTracker(redis_client=mock_redis, fail_silently=True)

        # Should not raise exception
        tracker.track_api_call(
            model_name="test",
            input_tokens=100,
            output_tokens=50,
            cost=0.001,
            operation="test"
        )
```

### Success Criteria
- [ ] Redis operations mocked correctly
- [ ] Aggregation logic verified
- [ ] Error handling tested
- [ ] Data retention (30-day) logic tested

---

### Task 5A.4: VectorStore Unit Tests

**File:** `backend/tests/unit/test_vector_store_unit.py`

**Test Cases:**
```python
import pytest
from backend.services.vector_store import ContractVectorStore

class TestVectorStoreUnit:

    def test_chunking_creates_correct_sizes(self):
        """Test text chunking with specified size and overlap."""
        store = ContractVectorStore(persist_directory=None)  # In-memory

        text = "A" * 2500  # 2.5x chunk size
        chunks = store._chunk_text(text, chunk_size=1000, overlap=200)

        assert len(chunks) == 3
        assert all(len(chunk) <= 1000 for chunk in chunks)

    def test_chunking_preserves_sentence_boundaries(self):
        """Test that chunks prefer to break at sentence boundaries."""
        store = ContractVectorStore(persist_directory=None)

        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = store._chunk_text(text, chunk_size=30, overlap=5)

        # Chunks should end at periods when possible
        for chunk in chunks[:-1]:  # All but last
            assert chunk.strip().endswith('.') or len(chunk) == 30

    def test_chunking_handles_empty_text(self):
        """Test chunking with empty string."""
        store = ContractVectorStore(persist_directory=None)

        chunks = store._chunk_text("", chunk_size=1000, overlap=200)
        assert chunks == []

    def test_metadata_preserved_in_chunks(self, sample_contract_text):
        """Test that metadata is attached to each chunk."""
        store = ContractVectorStore(persist_directory=None)

        result = store._prepare_chunks(
            text=sample_contract_text,
            contract_id="test-123",
            metadata={"filename": "contract.pdf"}
        )

        for chunk in result:
            assert chunk["metadata"]["contract_id"] == "test-123"
            assert chunk["metadata"]["filename"] == "contract.pdf"
```

### Success Criteria
- [ ] Chunking logic verified with various inputs
- [ ] Sentence boundary detection works
- [ ] Empty/edge cases handled
- [ ] Metadata preservation tested

---

## Group 5B: Backend Integration Tests

**Files to Create:**
- `backend/tests/integration/test_api_integration.py`
- `backend/tests/integration/test_workflow_integration.py`

### Task 5B.1: API Integration Tests (Mocked External Services)

**File:** `backend/tests/integration/test_api_integration.py`

```python
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
from backend.main import app

class TestAPIIntegration:

    @pytest.mark.asyncio
    async def test_upload_endpoint_validates_pdf(self):
        """Test that upload endpoint rejects non-PDF files."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/contracts/upload",
                files={"file": ("test.txt", b"not a pdf", "text/plain")}
            )

        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_endpoint_with_mocked_services(self):
        """Test upload flow with mocked external APIs."""
        with patch("backend.services.llamaparse_service.LlamaParseService") as mock_llama:
            with patch("backend.services.gemini_router.GeminiRouter") as mock_gemini:
                # Setup mocks
                mock_llama.return_value.parse_document = AsyncMock(
                    return_value="Parsed contract text"
                )
                mock_gemini.return_value.generate = AsyncMock(
                    return_value={
                        "text": '{"risk_score": 5, "risk_level": "medium"}',
                        "cost": 0.001,
                        "model_name": "gemini-2.5-flash"
                    }
                )

                async with AsyncClient(app=app, base_url="http://test") as client:
                    response = await client.post(
                        "/api/contracts/upload",
                        files={"file": ("test.pdf", b"%PDF-1.4 test content", "application/pdf")}
                    )

                assert response.status_code == 201
                data = response.json()
                assert "contract_id" in data
                assert "risk_analysis" in data

    @pytest.mark.asyncio
    async def test_query_endpoint_returns_answer(self):
        """Test Q&A endpoint returns structured answer."""
        with patch("backend.services.vector_store.ContractVectorStore") as mock_vector:
            with patch("backend.services.gemini_router.GeminiRouter") as mock_gemini:
                mock_vector.return_value.semantic_search = AsyncMock(
                    return_value=[{"text": "Payment terms: Net 30", "score": 0.9}]
                )
                mock_gemini.return_value.generate = AsyncMock(
                    return_value={
                        "text": "The payment terms are Net 30 days.",
                        "cost": 0.0005
                    }
                )

                async with AsyncClient(app=app, base_url="http://test") as client:
                    response = await client.post(
                        "/api/contracts/test-123/query",
                        json={"query": "What are the payment terms?"}
                    )

                assert response.status_code == 200
                assert "answer" in response.json()

    @pytest.mark.asyncio
    async def test_health_check_reports_service_status(self):
        """Test health endpoint reports all service statuses."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert "redis" in data["services"]
        assert "falkordb" in data["services"]
```

### Success Criteria
- [ ] File validation tested (PDF only)
- [ ] Upload flow works with mocked APIs
- [ ] Query endpoint returns structured response
- [ ] Health check reports all services
- [ ] Error responses are structured

---

### Task 5B.2: Workflow Integration Tests

**File:** `backend/tests/integration/test_workflow_integration.py`

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from backend.workflows.contract_analysis_workflow import ContractAnalysisWorkflow

class TestWorkflowIntegration:

    @pytest.mark.asyncio
    async def test_full_workflow_with_mocked_services(self):
        """Test complete workflow execution with mocked services."""
        with patch.multiple(
            "backend.workflows.contract_analysis_workflow",
            GeminiRouter=MagicMock(),
            LlamaParseService=MagicMock(),
            ContractVectorStore=MagicMock(),
            ContractGraphStore=MagicMock()
        ):
            workflow = ContractAnalysisWorkflow(initialize_stores=False)

            # Mock node implementations
            workflow.parse_document_node = AsyncMock(
                return_value={"parsed_document": "Test content"}
            )
            workflow.analyze_risk_node = AsyncMock(
                return_value={"risk_analysis": {"risk_score": 5}}
            )
            workflow.store_vectors_node = AsyncMock(
                return_value={"vector_ids": ["v1", "v2"]}
            )
            workflow.store_graph_node = AsyncMock(
                return_value={"graph_stored": True}
            )

            result = await workflow.run(
                contract_id="test-123",
                file_bytes=b"test",
                filename="test.pdf",
                query=None
            )

            assert result["risk_analysis"]["risk_score"] == 5
            assert result["graph_stored"] == True

    @pytest.mark.asyncio
    async def test_workflow_accumulates_errors(self):
        """Test that workflow accumulates errors without stopping."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        # Make parse fail
        workflow.parse_document_node = AsyncMock(
            return_value={
                "parsed_document": None,
                "errors": ["Parse failed: Invalid PDF"]
            }
        )

        result = await workflow.run(
            contract_id="test-123",
            file_bytes=b"invalid",
            filename="test.pdf",
            query=None
        )

        assert len(result.get("errors", [])) > 0
        assert any("Parse" in err for err in result["errors"])

    @pytest.mark.asyncio
    async def test_workflow_calculates_total_cost(self):
        """Test that workflow tracks total cost across all nodes."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        # Each node adds cost
        workflow.parse_document_node = AsyncMock(
            return_value={"total_cost": 0.001}
        )
        workflow.analyze_risk_node = AsyncMock(
            return_value={"total_cost": 0.003}  # Cumulative
        )

        result = await workflow.run(
            contract_id="test-123",
            file_bytes=b"test",
            filename="test.pdf",
            query=None
        )

        assert result["total_cost"] >= 0.003
```

### Success Criteria
- [ ] Full workflow executes with mocks
- [ ] Error accumulation works
- [ ] Cost tracking aggregates correctly
- [ ] State transitions verified

---

## Group 5C: Frontend Tests

**Files to Create:**
- `frontend/src/__tests__/api.test.ts`
- `frontend/src/__tests__/components/FileUpload.test.tsx`
- `frontend/vitest.config.ts`

### Task 5C.1: Frontend Test Setup

**File:** `frontend/vitest.config.ts`

```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/__tests__/setup.ts'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

**File:** `frontend/src/__tests__/setup.ts`

```typescript
import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
  useParams: () => ({
    contractId: 'test-123',
  }),
}))
```

**Package.json addition:**
```json
{
  "devDependencies": {
    "vitest": "^1.0.0",
    "@testing-library/react": "^14.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "jsdom": "^22.0.0"
  },
  "scripts": {
    "test": "vitest",
    "test:coverage": "vitest --coverage"
  }
}
```

### Success Criteria
- [ ] Vitest configured for Next.js
- [ ] React Testing Library available
- [ ] Path aliases work in tests
- [ ] `npm test` runs successfully

---

### Task 5C.2: API Client Tests

**File:** `frontend/src/__tests__/api.test.ts`

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'
import { uploadContract, queryContract, getContractDetails } from '@/lib/api'

vi.mock('axios')
const mockedAxios = axios as jest.Mocked<typeof axios>

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('uploadContract', () => {
    it('should upload file and return contract data', async () => {
      const mockResponse = {
        data: {
          contract_id: 'test-123',
          risk_analysis: { risk_score: 5 },
        },
      }
      mockedAxios.post.mockResolvedValueOnce(mockResponse)

      const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })
      const result = await uploadContract(file)

      expect(result.contract_id).toBe('test-123')
      expect(mockedAxios.post).toHaveBeenCalledWith(
        '/api/contracts/upload',
        expect.any(FormData),
        expect.objectContaining({
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      )
    })

    it('should handle upload errors gracefully', async () => {
      mockedAxios.post.mockRejectedValueOnce(new Error('Network error'))

      const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })

      await expect(uploadContract(file)).rejects.toThrow()
    })
  })

  describe('queryContract', () => {
    it('should send query and return answer', async () => {
      const mockResponse = {
        data: {
          answer: 'Payment terms are Net 30',
          cost: 0.001,
        },
      }
      mockedAxios.post.mockResolvedValueOnce(mockResponse)

      const result = await queryContract('test-123', 'What are payment terms?')

      expect(result.answer).toBe('Payment terms are Net 30')
    })
  })
})
```

### Success Criteria
- [ ] Upload function tested with mock
- [ ] Query function tested with mock
- [ ] Error handling verified
- [ ] Request format validated

---

### Task 5C.3: FileUpload Component Tests

**File:** `frontend/src/__tests__/components/FileUpload.test.tsx`

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FileUpload from '@/components/FileUpload'

describe('FileUpload Component', () => {
  it('should render upload zone', () => {
    render(<FileUpload onUploadComplete={vi.fn()} />)

    expect(screen.getByText(/drag and drop/i)).toBeInTheDocument()
  })

  it('should reject non-PDF files', async () => {
    const onUpload = vi.fn()
    render(<FileUpload onUploadComplete={onUpload} />)

    const file = new File(['test'], 'test.txt', { type: 'text/plain' })
    const input = screen.getByLabelText(/upload/i) || screen.getByRole('button')

    // Simulate file selection
    await userEvent.upload(input, file)

    expect(screen.getByText(/pdf/i)).toBeInTheDocument()
    expect(onUpload).not.toHaveBeenCalled()
  })

  it('should show progress during upload', async () => {
    const onUpload = vi.fn()
    render(<FileUpload onUploadComplete={onUpload} />)

    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })
    const input = screen.getByLabelText(/upload/i) || screen.getByRole('button')

    await userEvent.upload(input, file)

    // Should show progress indicator
    await waitFor(() => {
      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })
  })
})
```

### Success Criteria
- [ ] Component renders correctly
- [ ] File validation works
- [ ] Progress shown during upload
- [ ] Success callback fires

---

## Test Execution Commands

```bash
# Backend tests
cd backend
pytest tests/unit/ -v                    # Unit tests only
pytest tests/integration/ -v             # Integration tests only
pytest tests/ -v --cov=. --cov-report=html  # All with coverage

# Frontend tests
cd frontend
npm test                                 # Run all tests
npm test -- --coverage                   # With coverage
npm test -- --watch                      # Watch mode
```

---

## Completion Checklist

### Group 5A: Backend Unit Tests
- [ ] Task 5A.1: Test fixtures setup
- [ ] Task 5A.2: GeminiRouter unit tests
- [ ] Task 5A.3: CostTracker unit tests
- [ ] Task 5A.4: VectorStore unit tests

### Group 5B: Backend Integration Tests
- [ ] Task 5B.1: API integration tests
- [ ] Task 5B.2: Workflow integration tests

### Group 5C: Frontend Tests
- [ ] Task 5C.1: Test setup (Vitest)
- [ ] Task 5C.2: API client tests
- [ ] Task 5C.3: FileUpload component tests

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Backend Unit Test Coverage | ~10% | 60%+ |
| Backend Integration Tests | 0 | 5+ |
| Frontend Tests | 0 | 5+ |
| Critical Path Coverage | 0% | 100% |
