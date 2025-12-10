"""
Shared pytest fixtures for backend tests.

Provides reusable mocks and test data for unit and integration tests.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


@pytest.fixture
def mock_redis():
    """Mock Redis client for cost tracker tests."""
    redis = MagicMock()

    # Mock basic Redis operations
    redis.hset = MagicMock()
    redis.hgetall = MagicMock(return_value={})
    redis.expire = MagicMock()
    redis.hincrby = MagicMock()
    redis.hincrbyfloat = MagicMock()
    redis.ping = MagicMock(return_value=True)
    redis.delete = MagicMock()

    # Mock pipeline
    pipeline_mock = MagicMock()
    pipeline_mock.hincrby = MagicMock(return_value=pipeline_mock)
    pipeline_mock.hincrbyfloat = MagicMock(return_value=pipeline_mock)
    pipeline_mock.expire = MagicMock(return_value=pipeline_mock)
    pipeline_mock.execute = MagicMock(return_value=[])
    redis.pipeline = MagicMock(return_value=pipeline_mock)

    return redis


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response with usage metadata."""
    response = MagicMock()
    response.text = "Test response from Gemini"

    # Mock usage metadata
    usage_metadata = MagicMock()
    usage_metadata.prompt_token_count = 100
    usage_metadata.candidates_token_count = 50
    usage_metadata.total_token_count = 150
    usage_metadata.thinking_token_count = 0

    response.usage_metadata = usage_metadata
    return response


@pytest.fixture
def mock_gemini_response_with_thinking():
    """Mock Gemini API response with thinking tokens for reasoning models."""
    response = MagicMock()
    response.text = "Deep reasoning response from Gemini"

    # Mock usage metadata with thinking tokens
    usage_metadata = MagicMock()
    usage_metadata.prompt_token_count = 200
    usage_metadata.candidates_token_count = 100
    usage_metadata.thinking_token_count = 500
    usage_metadata.total_token_count = 800

    response.usage_metadata = usage_metadata
    return response


@pytest.fixture
def sample_contract_text():
    """Sample contract text for testing."""
    return """
SERVICE AGREEMENT

This Agreement is entered into as of January 1, 2025 between:

Party A: Acme Corporation, a Delaware corporation ("Client")
Party B: TechServ Inc., a California corporation ("Provider")

RECITALS

WHEREAS, Client desires to engage Provider to provide certain technical services;
WHEREAS, Provider agrees to provide such services on the terms set forth herein.

NOW, THEREFORE, in consideration of the mutual covenants contained herein, the parties agree:

1. PAYMENT TERMS

1.1 Payment Schedule
Payment shall be made within Net 30 days of invoice date. Late payments will incur
a 1.5% monthly interest charge.

1.2 Rates
The hourly rate for services is $150 per hour. Travel expenses will be reimbursed
at actual cost with prior approval.

2. LIABILITY AND INDEMNIFICATION

2.1 Limitation of Liability
Provider's total liability under this Agreement shall not exceed $1,000,000 in the
aggregate. Provider shall not be liable for consequential, incidental, or punitive damages.

2.2 Indemnification
Each party shall indemnify the other against third-party claims arising from its
breach of this Agreement or negligent acts.

3. TERMINATION

3.1 Termination for Convenience
Either party may terminate this Agreement with 30 days written notice.

3.2 Termination for Cause
Either party may terminate immediately upon material breach by the other party if
such breach is not cured within 15 days of written notice.

4. CONFIDENTIALITY

Both parties agree to maintain confidentiality of proprietary information disclosed
during the term of this Agreement for a period of 3 years following termination.

5. INTELLECTUAL PROPERTY

All work product created by Provider shall be owned by Client upon full payment.
Provider retains rights to its pre-existing intellectual property and methodologies.

6. GOVERNING LAW

This Agreement shall be governed by the laws of the State of Delaware without
regard to conflicts of law principles.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first written above.

ACME CORPORATION                    TECHSERV INC.

By: ____________________            By: ____________________
Name: John Doe                      Name: Jane Smith
Title: CEO                          Title: President
Date: January 1, 2025               Date: January 1, 2025
"""


@pytest.fixture
def sample_contract_metadata():
    """Sample contract metadata for testing."""
    return {
        "filename": "service_agreement.pdf",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "parties": ["Acme Corporation", "TechServ Inc."],
        "contract_type": "Service Agreement",
        "effective_date": "2025-01-01"
    }


@pytest.fixture
def mock_chroma_collection():
    """Mock ChromaDB collection for vector store tests."""
    collection = MagicMock()
    collection.name = "legal_contracts"
    collection.count = MagicMock(return_value=0)
    collection.add = MagicMock()
    collection.query = MagicMock(return_value={
        'ids': [[]],
        'documents': [[]],
        'metadatas': [[]],
        'distances': [[]]
    })
    collection.get = MagicMock(return_value={'ids': []})
    collection.delete = MagicMock()
    return collection


@pytest.fixture
def mock_genai_embed_content():
    """Mock Google genai.embed_content function."""
    def embed_mock(model, content, task_type=None):
        if isinstance(content, list):
            # Batch embedding
            return {
                'embedding': [[0.1] * 768 for _ in content]
            }
        else:
            # Single embedding
            return {
                'embedding': [0.1] * 768
            }

    return embed_mock


@pytest.fixture
def sample_risk_analysis():
    """Sample risk analysis result for testing."""
    return {
        "risk_score": 5,
        "risk_level": "medium",
        "key_risks": [
            {
                "category": "liability",
                "description": "Limited liability cap of $1M may be insufficient",
                "severity": "medium"
            },
            {
                "category": "payment",
                "description": "Net 30 payment terms with late fees",
                "severity": "low"
            }
        ],
        "recommendations": [
            "Consider increasing liability cap for complex projects",
            "Ensure payment schedule aligns with cash flow"
        ]
    }


@pytest.fixture
def sample_api_call_data():
    """Sample API call data for cost tracking tests."""
    return {
        "model_name": "gemini-2.5-flash",
        "input_tokens": 1000,
        "output_tokens": 500,
        "thinking_tokens": 0,
        "cost": 0.00045,
        "operation_type": "risk_analysis",
        "contract_id": "test-contract-123"
    }


# FalkorDB Integration Test Fixtures

import os

# Configurable FalkorDB test settings
FALKORDB_TEST_HOST = os.getenv("FALKORDB_TEST_HOST", "localhost")
FALKORDB_TEST_PORT = int(os.getenv("FALKORDB_TEST_PORT", "6381"))


def is_falkordb_available() -> bool:
    """Check if FalkorDB is available for testing."""
    try:
        from falkordb import FalkorDB
        db = FalkorDB(host=FALKORDB_TEST_HOST, port=FALKORDB_TEST_PORT)
        # Verify the graph module is loaded
        graph = db.select_graph("_test_connection")
        graph.query("RETURN 1")
        return True
    except Exception:
        return False


@pytest.fixture
def sample_graph_contract():
    """Sample contract node for graph store testing."""
    from backend.models.graph_schemas import ContractNode
    from uuid import uuid4

    return ContractNode(
        contract_id=f"test_contract_{uuid4().hex[:8]}",
        filename="test_agreement.pdf",
        upload_date=datetime.now(timezone.utc),
        risk_score=6.5,
        risk_level="medium",
        payment_amount="$50,000",
        payment_frequency="monthly",
        has_termination_clause=True,
        liability_cap="$100,000"
    )


@pytest.fixture
def sample_graph_companies():
    """Sample company nodes for graph store testing."""
    from backend.models.graph_schemas import CompanyNode

    return [
        CompanyNode(name="Acme Corp", role="vendor", company_id="acme_001"),
        CompanyNode(name="Client Inc", role="client", company_id="client_001"),
    ]


@pytest.fixture
def sample_graph_clauses():
    """Sample clause nodes for graph store testing."""
    from backend.models.graph_schemas import ClauseNode

    return [
        ClauseNode(
            section_name="Payment Terms",
            content="Payment shall be made within 30 days of invoice.",
            clause_type="payment",
            importance="high"
        ),
        ClauseNode(
            section_name="Termination",
            content="Either party may terminate with 30 days notice.",
            clause_type="termination",
            importance="medium"
        ),
    ]


@pytest.fixture
def sample_graph_risk_factors():
    """Sample risk factor nodes for graph store testing."""
    from backend.models.graph_schemas import RiskFactorNode

    return [
        RiskFactorNode(
            concern="Limited liability cap may be insufficient",
            risk_level="medium",
            section="Liability",
            recommendation="Consider negotiating higher cap"
        ),
    ]
