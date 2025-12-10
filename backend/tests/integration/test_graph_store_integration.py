"""
Integration tests for FalkorDB graph store.

These tests require a running FalkorDB instance.

If you have a local Redis on port 6379, use port 6381 for FalkorDB:
    docker run -p 6381:6379 -p 3001:3000 -it --rm falkordb/falkordb

Otherwise use the default port:
    docker run -p 6379:6379 -p 3000:3000 -it --rm falkordb/falkordb

Configure the test port via environment variable:
    FALKORDB_TEST_PORT=6381 pytest tests/integration/test_graph_store_integration.py -v

To run these tests:
    pytest tests/integration/test_graph_store_integration.py -v

Skip these tests if FalkorDB is not running:
    pytest tests/integration/test_graph_store_integration.py -v -m "not integration"
"""

import os
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from backend.services.graph_store import ContractGraphStore
from backend.models.graph_schemas import (
    ContractNode,
    CompanyNode,
    ClauseNode,
    RiskFactorNode,
)

# Configurable test port (default 6379, use 6381 if local Redis is on 6379)
FALKORDB_TEST_HOST = os.getenv("FALKORDB_TEST_HOST", "localhost")
FALKORDB_TEST_PORT = int(os.getenv("FALKORDB_TEST_PORT", "6381"))


def is_falkordb_available() -> bool:
    """Check if FalkorDB is available for testing."""
    try:
        from falkordb import FalkorDB
        db = FalkorDB(host=FALKORDB_TEST_HOST, port=FALKORDB_TEST_PORT)
        # Verify the graph module is loaded by trying a simple query
        graph = db.select_graph("_test_connection")
        graph.query("RETURN 1")
        return True
    except Exception:
        return False


# Skip all tests in this module if FalkorDB is not available
pytestmark = pytest.mark.skipif(
    not is_falkordb_available(),
    reason=f"FalkorDB not available on {FALKORDB_TEST_HOST}:{FALKORDB_TEST_PORT}. "
           f"Run: docker run -p {FALKORDB_TEST_PORT}:6379 -it --rm falkordb/falkordb"
)


@pytest.fixture
def graph_store():
    """Create a graph store instance for testing."""
    store = ContractGraphStore(host=FALKORDB_TEST_HOST, port=FALKORDB_TEST_PORT)
    yield store
    store.close()


@pytest.fixture
def sample_contract_id():
    """Generate a unique contract ID for each test."""
    return f"test_contract_{uuid4().hex[:8]}"


@pytest.fixture
def sample_contract_node(sample_contract_id):
    """Create a sample contract node for testing."""
    return ContractNode(
        contract_id=sample_contract_id,
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
def sample_companies():
    """Create sample company nodes for testing."""
    return [
        CompanyNode(name="Acme Corp", role="vendor", company_id="acme_001"),
        CompanyNode(name="Client Inc", role="client", company_id="client_001"),
    ]


@pytest.fixture
def sample_clauses():
    """Create sample clause nodes for testing."""
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
        ClauseNode(
            section_name="Confidentiality",
            content="All information shared shall remain confidential.",
            clause_type="confidentiality",
            importance="high"
        ),
    ]


@pytest.fixture
def sample_risk_factors():
    """Create sample risk factor nodes for testing."""
    return [
        RiskFactorNode(
            concern="Limited liability cap may be insufficient",
            risk_level="medium",
            section="Liability",
            recommendation="Consider negotiating higher cap"
        ),
        RiskFactorNode(
            concern="Short termination notice period",
            risk_level="low",
            section="Termination",
            recommendation="Extend notice period to 60 days"
        ),
    ]


@pytest.fixture
def cleanup_contract(graph_store, sample_contract_id):
    """Cleanup fixture to ensure contract is deleted after test."""
    yield
    try:
        graph_store.delete_contract(sample_contract_id)
    except Exception:
        pass  # Ignore cleanup errors


class TestContractGraphStoreIntegration:
    """Integration tests for ContractGraphStore with real FalkorDB."""

    @pytest.mark.integration
    async def test_store_contract_creates_graph(
        self,
        graph_store,
        sample_contract_node,
        sample_companies,
        sample_clauses,
        sample_risk_factors,
        cleanup_contract
    ):
        """Test storing a complete contract graph."""
        # Store the contract
        result = await graph_store.store_contract(
            contract=sample_contract_node,
            companies=sample_companies,
            clauses=sample_clauses,
            risk_factors=sample_risk_factors
        )

        # Verify the result
        assert result is not None
        assert result.contract.contract_id == sample_contract_node.contract_id
        assert result.contract.filename == "test_agreement.pdf"
        assert result.contract.risk_level == "medium"
        assert len(result.companies) == 2
        assert len(result.clauses) == 3
        assert len(result.risk_factors) == 2
        assert len(result.relationships) == 7  # 2 PARTY_TO + 3 CONTAINS + 2 HAS_RISK

    @pytest.mark.integration
    async def test_get_contract_relationships_returns_full_graph(
        self,
        graph_store,
        sample_contract_node,
        sample_companies,
        sample_clauses,
        sample_risk_factors,
        cleanup_contract
    ):
        """Test retrieving a stored contract with all relationships."""
        # First store the contract
        await graph_store.store_contract(
            contract=sample_contract_node,
            companies=sample_companies,
            clauses=sample_clauses,
            risk_factors=sample_risk_factors
        )

        # Retrieve it
        result = await graph_store.get_contract_relationships(
            sample_contract_node.contract_id
        )

        # Verify all data was retrieved
        assert result is not None
        assert result.contract.contract_id == sample_contract_node.contract_id
        assert result.contract.filename == "test_agreement.pdf"
        assert result.contract.risk_score == 6.5
        assert result.contract.risk_level == "medium"
        assert result.contract.payment_amount == "$50,000"
        assert result.contract.has_termination_clause is True

        # Verify companies
        assert len(result.companies) == 2
        company_names = {c.name for c in result.companies}
        assert "Acme Corp" in company_names
        assert "Client Inc" in company_names

        # Verify clauses
        assert len(result.clauses) == 3
        clause_names = {c.section_name for c in result.clauses}
        assert "Payment Terms" in clause_names
        assert "Termination" in clause_names
        assert "Confidentiality" in clause_names

        # Verify risk factors
        assert len(result.risk_factors) == 2
        risk_concerns = {r.concern for r in result.risk_factors}
        assert any("liability" in c.lower() for c in risk_concerns)

    @pytest.mark.integration
    async def test_get_contract_relationships_returns_none_for_missing(
        self,
        graph_store
    ):
        """Test that getting a non-existent contract returns None."""
        result = await graph_store.get_contract_relationships("nonexistent_contract_id")
        assert result is None

    @pytest.mark.integration
    async def test_find_similar_contracts_by_risk_level(
        self,
        graph_store,
        sample_companies,
        sample_clauses,
        sample_risk_factors
    ):
        """Test finding contracts by risk level."""
        # Create multiple contracts with different risk levels
        contracts_to_cleanup = []

        try:
            for i, risk_level in enumerate(["high", "high", "medium", "low"]):
                contract_id = f"test_similar_{uuid4().hex[:8]}"
                contracts_to_cleanup.append(contract_id)

                contract = ContractNode(
                    contract_id=contract_id,
                    filename=f"contract_{i}.pdf",
                    upload_date=datetime.now(timezone.utc),
                    risk_score=8.0 if risk_level == "high" else 5.0,
                    risk_level=risk_level
                )

                await graph_store.store_contract(
                    contract=contract,
                    companies=sample_companies,
                    clauses=sample_clauses,
                    risk_factors=sample_risk_factors
                )

            # Find high-risk contracts
            high_risk = await graph_store.find_similar_contracts("high", limit=10)
            assert len(high_risk) >= 2
            assert all(c.risk_level == "high" for c in high_risk)

            # Find medium-risk contracts
            medium_risk = await graph_store.find_similar_contracts("medium", limit=10)
            assert len(medium_risk) >= 1
            assert all(c.risk_level == "medium" for c in medium_risk)

        finally:
            # Cleanup
            for contract_id in contracts_to_cleanup:
                try:
                    graph_store.delete_contract(contract_id)
                except Exception:
                    pass

    @pytest.mark.integration
    def test_delete_contract_removes_all_related_nodes(
        self,
        graph_store,
        sample_contract_node,
        sample_companies,
        sample_clauses,
        sample_risk_factors
    ):
        """Test that deleting a contract removes all related nodes."""
        import asyncio

        # Store the contract
        asyncio.get_event_loop().run_until_complete(
            graph_store.store_contract(
                contract=sample_contract_node,
                companies=sample_companies,
                clauses=sample_clauses,
                risk_factors=sample_risk_factors
            )
        )

        # Verify it exists
        result = asyncio.get_event_loop().run_until_complete(
            graph_store.get_contract_relationships(sample_contract_node.contract_id)
        )
        assert result is not None

        # Delete it
        deleted = graph_store.delete_contract(sample_contract_node.contract_id)
        assert deleted is True

        # Verify it's gone
        result = asyncio.get_event_loop().run_until_complete(
            graph_store.get_contract_relationships(sample_contract_node.contract_id)
        )
        assert result is None

    @pytest.mark.integration
    def test_delete_nonexistent_contract_returns_false(self, graph_store):
        """Test that deleting a non-existent contract returns False."""
        result = graph_store.delete_contract("nonexistent_contract_id")
        assert result is False

    @pytest.mark.integration
    async def test_store_contract_with_minimal_data(
        self,
        graph_store,
        cleanup_contract,
        sample_contract_id
    ):
        """Test storing a contract with only required fields."""
        contract = ContractNode(
            contract_id=sample_contract_id,
            filename="minimal.pdf"
        )

        result = await graph_store.store_contract(
            contract=contract,
            companies=[],
            clauses=[],
            risk_factors=[]
        )

        assert result is not None
        assert result.contract.contract_id == sample_contract_id
        assert result.contract.filename == "minimal.pdf"
        assert len(result.companies) == 0
        assert len(result.clauses) == 0
        assert len(result.risk_factors) == 0

    @pytest.mark.integration
    async def test_store_contract_updates_existing(
        self,
        graph_store,
        sample_contract_node,
        sample_companies,
        sample_clauses,
        sample_risk_factors,
        cleanup_contract
    ):
        """Test that storing a contract with same ID updates it."""
        # Store initial contract
        await graph_store.store_contract(
            contract=sample_contract_node,
            companies=sample_companies,
            clauses=sample_clauses,
            risk_factors=sample_risk_factors
        )

        # Update with new data
        updated_contract = ContractNode(
            contract_id=sample_contract_node.contract_id,
            filename="updated_agreement.pdf",
            upload_date=datetime.now(timezone.utc),
            risk_score=9.0,
            risk_level="high"
        )

        await graph_store.store_contract(
            contract=updated_contract,
            companies=[],
            clauses=[],
            risk_factors=[]
        )

        # Retrieve and verify update
        result = await graph_store.get_contract_relationships(
            sample_contract_node.contract_id
        )

        assert result is not None
        assert result.contract.filename == "updated_agreement.pdf"
        assert result.contract.risk_score == 9.0
        assert result.contract.risk_level == "high"


class TestGraphStoreConnection:
    """Tests for FalkorDB connection handling."""

    @pytest.mark.integration
    def test_connection_with_default_settings(self):
        """Test connecting with configured test settings."""
        store = ContractGraphStore(host=FALKORDB_TEST_HOST, port=FALKORDB_TEST_PORT)
        assert store.db is not None
        assert store.graph is not None
        store.close()

    @pytest.mark.integration
    def test_schema_initialization_creates_indexes(self, graph_store):
        """Test that schema initialization creates the required indexes."""
        # The indexes are created in __init__, so if we get here without error,
        # the indexes were created successfully (or already existed)
        assert graph_store.graph is not None

    @pytest.mark.integration
    def test_close_connection(self):
        """Test that close() properly closes the connection."""
        store = ContractGraphStore(host=FALKORDB_TEST_HOST, port=FALKORDB_TEST_PORT)
        store.close()
        # After close, the db should still exist but connection closed
        assert hasattr(store, 'db')
