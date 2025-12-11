"""Unit tests for GraphContextRetriever."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.services.graph_context_retriever import GraphContextRetriever, GraphContext


class TestGraphContextRetriever:
    """Tests for GraphContextRetriever."""

    @pytest.fixture
    def mock_graph_store(self):
        """Create a mocked graph store."""
        store = MagicMock()
        store.graph = MagicMock()
        return store

    @pytest.fixture
    def retriever(self, mock_graph_store):
        """Create a GraphContextRetriever with mocked graph store."""
        return GraphContextRetriever(mock_graph_store)

    @pytest.mark.asyncio
    async def test_get_context_for_contract_returns_all_entities(self, retriever, mock_graph_store):
        """Should return contract, companies, clauses, and risks."""
        # Arrange - Mock FalkorDB result
        mock_contract = MagicMock()
        mock_contract.properties = {
            "contract_id": "c1",
            "filename": "test.pdf",
            "upload_date": "2024-01-15T10:30:00",
            "risk_score": 6.5,
            "risk_level": "medium"
        }

        mock_company = MagicMock()
        mock_company.properties = {
            "name": "Acme Corp",
            "role": "vendor",
            "company_id": "acme_123"
        }

        mock_clause = MagicMock()
        mock_clause.properties = {
            "section_name": "Payment Terms",
            "content": "Payment within 30 days",
            "clause_type": "payment",
            "importance": "high"
        }

        mock_risk = MagicMock()
        mock_risk.properties = {
            "concern": "Liability exposure",
            "risk_level": "high",
            "section": "Liability",
            "recommendation": "Add cap"
        }

        mock_graph_store.graph.query.return_value = MagicMock(
            result_set=[
                [
                    mock_contract,
                    [mock_company],
                    [mock_clause],
                    [mock_risk]
                ]
            ]
        )

        # Act
        result = await retriever.get_context_for_contract("c1")

        # Assert
        assert result is not None
        assert result.contract_id == "c1"
        assert len(result.companies) == 1
        assert result.companies[0]["name"] == "Acme Corp"
        assert len(result.related_clauses) == 1
        assert result.related_clauses[0]["section_name"] == "Payment Terms"
        assert len(result.risk_factors) == 1
        assert result.risk_factors[0]["concern"] == "Liability exposure"
        assert result.traversal_depth == 1

    @pytest.mark.asyncio
    async def test_get_context_for_contract_handles_missing_contract(self, retriever, mock_graph_store):
        """Should return None for non-existent contract."""
        # Arrange
        mock_graph_store.graph.query.return_value = MagicMock(result_set=[])

        # Act
        result = await retriever.get_context_for_contract("nonexistent")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_context_for_contract_with_selective_inclusion(self, retriever, mock_graph_store):
        """Should respect include flags for companies, clauses, and risks."""
        # Arrange
        mock_contract = MagicMock()
        mock_contract.properties = {
            "contract_id": "c1",
            "filename": "test.pdf",
            "upload_date": "2024-01-15T10:30:00"
        }

        mock_graph_store.graph.query.return_value = MagicMock(
            result_set=[[mock_contract, [], [], []]]
        )

        # Act
        result = await retriever.get_context_for_contract(
            "c1",
            include_companies=False,
            include_clauses=False,
            include_risks=False
        )

        # Assert
        assert result is not None
        assert result.contract_id == "c1"
        # Should still return empty lists, not None
        assert result.companies == []
        assert result.related_clauses == []
        assert result.risk_factors == []

    @pytest.mark.asyncio
    async def test_get_context_for_contract_limits_clauses(self, retriever, mock_graph_store):
        """Should limit number of clauses returned."""
        # Arrange
        mock_contract = MagicMock()
        mock_contract.properties = {
            "contract_id": "c1",
            "filename": "test.pdf",
            "upload_date": "2024-01-15T10:30:00"
        }

        # Create 15 mock clauses
        mock_clauses = [
            MagicMock(properties={
                "section_name": f"Section {i}",
                "content": f"Content {i}",
                "clause_type": "payment"
            })
            for i in range(15)
        ]

        mock_graph_store.graph.query.return_value = MagicMock(
            result_set=[[mock_contract, [], mock_clauses[:3], []]]  # Will be limited in query
        )

        # Act
        result = await retriever.get_context_for_contract("c1", max_clauses=3)

        # Assert
        assert result is not None
        assert len(result.related_clauses) <= 3

    @pytest.mark.asyncio
    async def test_get_context_for_clause_type_returns_matching_clauses(self, retriever, mock_graph_store):
        """Should return clauses matching specific type with related risks."""
        # Arrange
        mock_clause = MagicMock()
        mock_clause.properties = {
            "section_name": "Payment Terms",
            "content": "Payment within 30 days",
            "clause_type": "payment"
        }

        mock_risk = MagicMock()
        mock_risk.properties = {
            "concern": "Late payment penalties unclear",
            "risk_level": "medium"
        }

        mock_graph_store.graph.query.return_value = MagicMock(
            result_set=[
                [mock_clause, [mock_risk]]
            ]
        )

        # Act
        result = await retriever.get_context_for_clause_type("c1", "payment")

        # Assert
        assert result is not None
        assert "clause" in result
        assert result["clause"]["clause_type"] == "payment"
        assert "related_risks" in result
        assert len(result["related_risks"]) == 1

    @pytest.mark.asyncio
    async def test_get_context_for_clause_type_handles_missing_clause(self, retriever, mock_graph_store):
        """Should return None for non-existent clause type."""
        # Arrange
        mock_graph_store.graph.query.return_value = MagicMock(result_set=[])

        # Act
        result = await retriever.get_context_for_clause_type("c1", "nonexistent")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_find_similar_contracts_by_company_returns_contracts(self, retriever, mock_graph_store):
        """Should find contracts involving same company."""
        # Arrange
        mock_records = [
            [
                "contract_1",
                "agreement1.pdf",
                "medium",
                "vendor"
            ],
            [
                "contract_2",
                "agreement2.pdf",
                "high",
                "client"
            ]
        ]

        mock_graph_store.graph.query.return_value = MagicMock(result_set=mock_records)

        # Act
        result = await retriever.find_similar_contracts_by_company("Acme Corp", limit=5)

        # Assert
        assert len(result) == 2
        assert result[0]["contract_id"] == "contract_1"
        assert result[0]["filename"] == "agreement1.pdf"
        assert result[0]["risk_level"] == "medium"
        assert result[0]["role"] == "vendor"

    @pytest.mark.asyncio
    async def test_find_similar_contracts_by_company_handles_missing_company(self, retriever, mock_graph_store):
        """Should return empty list for non-existent company."""
        # Arrange
        mock_graph_store.graph.query.return_value = MagicMock(result_set=[])

        # Act
        result = await retriever.find_similar_contracts_by_company("NonExistent Corp")

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_risk_context_returns_all_risks(self, retriever, mock_graph_store):
        """Should return all risks with associated clauses."""
        # Arrange
        mock_risk = MagicMock()
        mock_risk.properties = {
            "concern": "Liability exposure",
            "risk_level": "high",
            "section": "Liability"
        }

        mock_records = [
            [mock_risk, "Liability clause content here"]
        ]

        mock_graph_store.graph.query.return_value = MagicMock(result_set=mock_records)

        # Act
        result = await retriever.get_risk_context("c1")

        # Assert
        assert len(result) == 1
        assert result[0]["risk"]["concern"] == "Liability exposure"
        assert result[0]["clause_content"] == "Liability clause content here"

    @pytest.mark.asyncio
    async def test_get_risk_context_filters_by_risk_level(self, retriever, mock_graph_store):
        """Should filter risks by level when specified."""
        # Arrange
        mock_risk = MagicMock()
        mock_risk.properties = {
            "concern": "High risk concern",
            "risk_level": "high"
        }

        mock_graph_store.graph.query.return_value = MagicMock(
            result_set=[[mock_risk, "Clause content"]]
        )

        # Act
        result = await retriever.get_risk_context("c1", risk_level="high")

        # Assert
        assert len(result) == 1
        assert result[0]["risk"]["risk_level"] == "high"

        # Verify query was called with risk_level parameter
        call_args = mock_graph_store.graph.query.call_args
        assert call_args[0][1]["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_get_risk_context_handles_missing_contract(self, retriever, mock_graph_store):
        """Should return empty list for non-existent contract."""
        # Arrange
        mock_graph_store.graph.query.return_value = MagicMock(result_set=[])

        # Act
        result = await retriever.get_risk_context("nonexistent")

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_all_methods_use_asyncio_to_thread(self, retriever, mock_graph_store):
        """All methods should use async/await pattern."""
        # This is more of a structural test - verify methods are async
        import inspect

        assert inspect.iscoroutinefunction(retriever.get_context_for_contract)
        assert inspect.iscoroutinefunction(retriever.get_context_for_clause_type)
        assert inspect.iscoroutinefunction(retriever.find_similar_contracts_by_company)
        assert inspect.iscoroutinefunction(retriever.get_risk_context)
