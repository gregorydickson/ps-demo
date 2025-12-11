"""
Graph context retrieval for Graph RAG.

Traverses FalkorDB to expand context around semantic search results.
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from ..utils.logging import get_logger
    from ..utils.performance import log_execution_time
    from .api_resilience import falkordb_breaker, with_circuit_breaker, ServiceUnavailableError
except ImportError:
    from backend.utils.logging import get_logger
    from backend.utils.performance import log_execution_time
    from backend.services.api_resilience import falkordb_breaker, with_circuit_breaker, ServiceUnavailableError

logger = get_logger("graph_context_retriever")


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

    @log_execution_time("get_context_for_contract")
    @with_circuit_breaker(falkordb_breaker)
    async def get_context_for_contract(
        self,
        contract_id: str,
        include_companies: bool = True,
        include_clauses: bool = True,
        include_risks: bool = True,
        max_clauses: int = 10
    ) -> Optional[GraphContext]:
        """
        Retrieve full graph context for a contract.

        Args:
            contract_id: Contract to get context for
            include_companies: Include connected companies
            include_clauses: Include contract clauses
            include_risks: Include risk factors
            max_clauses: Maximum clauses to return

        Returns:
            GraphContext with all related entities, or None if contract not found

        Raises:
            ServiceUnavailableError: If FalkorDB circuit breaker is open
        """
        # Validate input
        if not contract_id or not isinstance(contract_id, str):
            raise ValueError("contract_id must be a non-empty string")

        def _query():
            """Synchronous query execution."""
            # Single Cypher query with OPTIONAL MATCH
            query = """
                MATCH (c:Contract {contract_id: $contract_id})
                OPTIONAL MATCH (co:Company)-[:PARTY_TO]->(c)
                OPTIONAL MATCH (c)-[:CONTAINS]->(cl:Clause)
                OPTIONAL MATCH (c)-[:HAS_RISK]->(r:RiskFactor)
                RETURN c,
                       collect(DISTINCT co) as companies,
                       collect(DISTINCT cl)[0..$max_clauses] as clauses,
                       collect(DISTINCT r) as risks
            """

            result = self.graph.query(
                query,
                {
                    'contract_id': contract_id,
                    'max_clauses': max_clauses
                }
            )

            return result

        try:
            # Execute query in thread pool
            result = await asyncio.to_thread(_query)

            if not result.result_set or len(result.result_set) == 0:
                logger.info("contract_not_found", contract_id=contract_id)
                return None

            row = result.result_set[0]

            # Parse contract node
            contract_node = row[0]
            contract_metadata = {
                "contract_id": contract_node.properties.get("contract_id"),
                "filename": contract_node.properties.get("filename"),
                "upload_date": contract_node.properties.get("upload_date"),
                "risk_score": contract_node.properties.get("risk_score"),
                "risk_level": contract_node.properties.get("risk_level"),
                "payment_amount": contract_node.properties.get("payment_amount"),
                "payment_frequency": contract_node.properties.get("payment_frequency"),
                "has_termination_clause": contract_node.properties.get("has_termination_clause"),
                "liability_cap": contract_node.properties.get("liability_cap")
            }

            # Parse companies (if included)
            companies = []
            if include_companies and row[1]:
                for company_node in row[1]:
                    if company_node is not None:
                        companies.append({
                            "name": company_node.properties.get("name"),
                            "role": company_node.properties.get("role"),
                            "company_id": company_node.properties.get("company_id")
                        })

            # Parse clauses (if included)
            clauses = []
            if include_clauses and row[2]:
                for clause_node in row[2]:
                    if clause_node is not None:
                        clauses.append({
                            "section_name": clause_node.properties.get("section_name"),
                            "content": clause_node.properties.get("content"),
                            "clause_type": clause_node.properties.get("clause_type"),
                            "importance": clause_node.properties.get("importance")
                        })

            # Parse risks (if included)
            risks = []
            if include_risks and row[3]:
                for risk_node in row[3]:
                    if risk_node is not None:
                        risks.append({
                            "concern": risk_node.properties.get("concern"),
                            "risk_level": risk_node.properties.get("risk_level"),
                            "section": risk_node.properties.get("section"),
                            "recommendation": risk_node.properties.get("recommendation")
                        })

            logger.info(
                "context_retrieved",
                contract_id=contract_id,
                companies=len(companies),
                clauses=len(clauses),
                risks=len(risks)
            )

            return GraphContext(
                contract_id=contract_id,
                contract_metadata=contract_metadata,
                companies=companies,
                related_clauses=clauses,
                risk_factors=risks,
                traversal_depth=1
            )

        except Exception as e:
            logger.error(
                "context_retrieval_error",
                contract_id=contract_id,
                error=str(e),
                error_type=type(e).__name__,
                include_companies=include_companies,
                include_clauses=include_clauses,
                include_risks=include_risks,
                max_clauses=max_clauses
            )
            raise RuntimeError(f"Failed to retrieve context for contract {contract_id}") from e

    @log_execution_time("get_context_for_clause_type")
    @with_circuit_breaker(falkordb_breaker)
    async def get_context_for_clause_type(
        self,
        contract_id: str,
        clause_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get context specific to a clause type (payment, termination, etc.).

        Returns clause content + related risks for that clause type.

        Args:
            contract_id: Contract to query
            clause_type: Type of clause to find

        Returns:
            Dict with clause and related_risks, or None if not found

        Raises:
            ServiceUnavailableError: If FalkorDB circuit breaker is open
        """
        # Validate inputs
        if not contract_id or not isinstance(contract_id, str):
            raise ValueError("contract_id must be a non-empty string")
        if not clause_type or not isinstance(clause_type, str):
            raise ValueError("clause_type must be a non-empty string")

        def _query():
            """Synchronous query execution."""
            query = """
                MATCH (c:Contract {contract_id: $contract_id})-[:CONTAINS]->(cl:Clause)
                WHERE cl.clause_type = $clause_type
                OPTIONAL MATCH (c)-[:HAS_RISK]->(r:RiskFactor)
                WHERE r.section = cl.section_name
                RETURN cl, collect(r) as related_risks
            """

            result = self.graph.query(
                query,
                {
                    'contract_id': contract_id,
                    'clause_type': clause_type
                }
            )

            return result

        try:
            # Execute query in thread pool
            result = await asyncio.to_thread(_query)

            if not result.result_set or len(result.result_set) == 0:
                logger.info(
                    "clause_type_not_found",
                    contract_id=contract_id,
                    clause_type=clause_type
                )
                return None

            row = result.result_set[0]

            # Parse clause
            clause_node = row[0]
            clause = {
                "section_name": clause_node.properties.get("section_name"),
                "content": clause_node.properties.get("content"),
                "clause_type": clause_node.properties.get("clause_type"),
                "importance": clause_node.properties.get("importance")
            }

            # Parse related risks
            related_risks = []
            if row[1]:
                for risk_node in row[1]:
                    if risk_node is not None:
                        related_risks.append({
                            "concern": risk_node.properties.get("concern"),
                            "risk_level": risk_node.properties.get("risk_level"),
                            "section": risk_node.properties.get("section"),
                            "recommendation": risk_node.properties.get("recommendation")
                        })

            logger.info(
                "clause_type_context_retrieved",
                contract_id=contract_id,
                clause_type=clause_type,
                risks=len(related_risks)
            )

            return {
                "clause": clause,
                "related_risks": related_risks
            }

        except Exception as e:
            logger.error(
                "clause_type_retrieval_error",
                contract_id=contract_id,
                clause_type=clause_type,
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"Failed to retrieve clause type '{clause_type}' for contract {contract_id}") from e

    @log_execution_time("find_similar_contracts_by_company")
    @with_circuit_breaker(falkordb_breaker)
    async def find_similar_contracts_by_company(
        self,
        company_name: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find other contracts involving the same company.

        Useful for cross-contract analysis.

        Args:
            company_name: Company name to search for
            limit: Maximum number of contracts to return

        Returns:
            List of contract dicts with metadata

        Raises:
            ServiceUnavailableError: If FalkorDB circuit breaker is open
        """
        # Validate inputs
        if not company_name or not isinstance(company_name, str):
            raise ValueError("company_name must be a non-empty string")
        if limit < 1:
            raise ValueError("limit must be at least 1")

        def _query():
            """Synchronous query execution."""
            query = """
                MATCH (co:Company {name: $company_name})-[:PARTY_TO]->(c:Contract)
                RETURN c.contract_id, c.filename, c.risk_level, co.role
                ORDER BY c.upload_date DESC
                LIMIT $limit
            """

            result = self.graph.query(
                query,
                {
                    'company_name': company_name,
                    'limit': limit
                }
            )

            return result

        try:
            # Execute query in thread pool
            result = await asyncio.to_thread(_query)

            if not result.result_set:
                logger.info("no_contracts_for_company", company_name=company_name)
                return []

            contracts = []
            for row in result.result_set:
                contracts.append({
                    "contract_id": row[0],
                    "filename": row[1],
                    "risk_level": row[2],
                    "role": row[3]
                })

            logger.info(
                "similar_contracts_found",
                company_name=company_name,
                count=len(contracts)
            )

            return contracts

        except Exception as e:
            logger.error(
                "similar_contracts_error",
                company_name=company_name,
                limit=limit,
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"Failed to find similar contracts for company '{company_name}'") from e

    @log_execution_time("get_risk_context")
    @with_circuit_breaker(falkordb_breaker)
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

        Returns:
            List of dicts with risk and clause_content

        Raises:
            ServiceUnavailableError: If FalkorDB circuit breaker is open
        """
        # Validate inputs
        if not contract_id or not isinstance(contract_id, str):
            raise ValueError("contract_id must be a non-empty string")
        if risk_level is not None and risk_level not in ('low', 'medium', 'high'):
            raise ValueError("risk_level must be one of: low, medium, high")

        def _query():
            """Synchronous query execution."""
            query = """
                MATCH (c:Contract {contract_id: $contract_id})-[:HAS_RISK]->(r:RiskFactor)
                WHERE $risk_level IS NULL OR r.risk_level = $risk_level
                OPTIONAL MATCH (c)-[:CONTAINS]->(cl:Clause)
                WHERE cl.section_name = r.section
                RETURN r, cl.content as clause_content
            """

            result = self.graph.query(
                query,
                {
                    'contract_id': contract_id,
                    'risk_level': risk_level
                }
            )

            return result

        try:
            # Execute query in thread pool
            result = await asyncio.to_thread(_query)

            if not result.result_set:
                logger.info(
                    "no_risks_found",
                    contract_id=contract_id,
                    risk_level=risk_level
                )
                return []

            risk_contexts = []
            for row in result.result_set:
                risk_node = row[0]
                clause_content = row[1]

                risk_contexts.append({
                    "risk": {
                        "concern": risk_node.properties.get("concern"),
                        "risk_level": risk_node.properties.get("risk_level"),
                        "section": risk_node.properties.get("section"),
                        "recommendation": risk_node.properties.get("recommendation")
                    },
                    "clause_content": clause_content
                })

            logger.info(
                "risk_context_retrieved",
                contract_id=contract_id,
                risk_level=risk_level,
                count=len(risk_contexts)
            )

            return risk_contexts

        except Exception as e:
            logger.error(
                "risk_context_error",
                contract_id=contract_id,
                risk_level=risk_level,
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"Failed to retrieve risk context for contract {contract_id}") from e
