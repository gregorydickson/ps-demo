"""
FalkorDB graph store for legal contract relationships.

Stores contracts as graph structures with companies, clauses, and risk factors
connected through typed relationships.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from falkordb import FalkorDB

from ..models.graph_schemas import (
    ContractNode,
    CompanyNode,
    ClauseNode,
    RiskFactorNode,
    ContractGraph,
    ContractRelationship
)

logger = logging.getLogger(__name__)


class ContractGraphStore:
    """
    FalkorDB graph store for legal contract knowledge graphs.

    Features:
    - Store contracts with relationships to parties, clauses, and risks
    - Query contract relationships
    - Traverse graph for insights
    - Automatic constraint and index management
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None
    ):
        """
        Initialize FalkorDB connection and create constraints/indexes.

        Args:
            host: Redis/FalkorDB host
            port: Redis/FalkorDB port
            password: Redis password (optional)
        """
        self.host = host or os.getenv("FALKORDB_HOST", "localhost")
        self.port = port or int(os.getenv("FALKORDB_PORT", "6379"))
        self.password = password or os.getenv("FALKORDB_PASSWORD", None)

        try:
            self.db = FalkorDB(
                host=self.host,
                port=self.port,
                password=self.password
            )
            self.graph = self.db.select_graph("contracts")

            logger.info(f"Connected to FalkorDB at {self.host}:{self.port}")

            # Initialize constraints and indexes
            self._initialize_schema()

        except Exception as e:
            logger.error(f"Failed to connect to FalkorDB: {e}")
            raise

    def _initialize_schema(self) -> None:
        """
        Create constraints and indexes for the graph schema.
        """
        constraints = [
            # Indexes for performance
            "CREATE INDEX FOR (c:Contract) ON (c.contract_id)",
            "CREATE INDEX FOR (c:Contract) ON (c.upload_date)",
            "CREATE INDEX FOR (c:Contract) ON (c.risk_level)",
            "CREATE INDEX FOR (co:Company) ON (co.name)",
            "CREATE INDEX FOR (cl:Clause) ON (cl.clause_type)",
            "CREATE INDEX FOR (r:RiskFactor) ON (r.risk_level)"
        ]

        for constraint in constraints:
            try:
                self.graph.query(constraint)
                logger.debug(f"Created index: {constraint[:50]}...")
            except Exception as e:
                logger.warning(f"Error creating index (may already exist): {e}")

    async def store_contract(
        self,
        contract: ContractNode,
        companies: List[CompanyNode],
        clauses: List[ClauseNode],
        risk_factors: List[RiskFactorNode]
    ) -> ContractGraph:
        """
        Store complete contract graph structure.

        Creates:
        - Contract node
        - Company nodes with PARTY_TO relationships
        - Clause nodes with CONTAINS relationships
        - RiskFactor nodes with HAS_RISK relationships

        Args:
            contract: Contract node data
            companies: List of party/company nodes
            clauses: List of clause nodes
            risk_factors: List of risk factor nodes

        Returns:
            ContractGraph with all stored nodes and relationships
        """
        relationships = []

        try:
            # Create contract node
            self.graph.query(
                """
                MERGE (c:Contract {contract_id: $contract_id})
                SET c.filename = $filename,
                    c.upload_date = $upload_date,
                    c.risk_score = $risk_score,
                    c.risk_level = $risk_level,
                    c.payment_amount = $payment_amount,
                    c.payment_frequency = $payment_frequency,
                    c.has_termination_clause = $has_termination_clause,
                    c.liability_cap = $liability_cap
                """,
                {
                    'contract_id': contract.contract_id,
                    'filename': contract.filename,
                    'upload_date': contract.upload_date.isoformat(),
                    'risk_score': contract.risk_score,
                    'risk_level': contract.risk_level,
                    'payment_amount': contract.payment_amount,
                    'payment_frequency': contract.payment_frequency,
                    'has_termination_clause': contract.has_termination_clause,
                    'liability_cap': contract.liability_cap
                }
            )
            logger.debug(f"Created Contract node: {contract.contract_id}")

            # Create company nodes and relationships
            for company in companies:
                self.graph.query(
                    """
                    MERGE (co:Company {name: $name})
                    SET co.role = $role,
                        co.company_id = $company_id
                    WITH co
                    MATCH (c:Contract {contract_id: $contract_id})
                    MERGE (co)-[r:PARTY_TO]->(c)
                    SET r.role = $role
                    """,
                    {
                        'name': company.name,
                        'role': company.role,
                        'company_id': company.company_id,
                        'contract_id': contract.contract_id
                    }
                )
                logger.debug(f"Created Company node: {company.name}")

                relationships.append(ContractRelationship(
                    type="PARTY_TO",
                    source="Company",
                    target="Contract",
                    properties={"role": company.role}
                ))

            # Create clause nodes and relationships
            for i, clause in enumerate(clauses):
                clause_id = f"{contract.contract_id}_clause_{i}"

                self.graph.query(
                    """
                    CREATE (cl:Clause {clause_id: $clause_id})
                    SET cl.section_name = $section_name,
                        cl.content = $content,
                        cl.clause_type = $clause_type,
                        cl.importance = $importance
                    WITH cl
                    MATCH (c:Contract {contract_id: $contract_id})
                    MERGE (c)-[r:CONTAINS]->(cl)
                    """,
                    {
                        'clause_id': clause_id,
                        'section_name': clause.section_name,
                        'content': clause.content,
                        'clause_type': clause.clause_type,
                        'importance': clause.importance,
                        'contract_id': contract.contract_id
                    }
                )
                logger.debug(f"Created Clause node: {clause.section_name}")

                relationships.append(ContractRelationship(
                    type="CONTAINS",
                    source="Contract",
                    target="Clause",
                    properties={}
                ))

            # Create risk factor nodes and relationships
            for i, risk in enumerate(risk_factors):
                risk_id = f"{contract.contract_id}_risk_{i}"

                self.graph.query(
                    """
                    CREATE (r:RiskFactor {risk_id: $risk_id})
                    SET r.concern = $concern,
                        r.risk_level = $risk_level,
                        r.section = $section,
                        r.recommendation = $recommendation
                    WITH r
                    MATCH (c:Contract {contract_id: $contract_id})
                    MERGE (c)-[rel:HAS_RISK]->(r)
                    SET rel.risk_level = $risk_level
                    """,
                    {
                        'risk_id': risk_id,
                        'concern': risk.concern,
                        'risk_level': risk.risk_level,
                        'section': risk.section,
                        'recommendation': risk.recommendation,
                        'contract_id': contract.contract_id
                    }
                )
                logger.debug(f"Created RiskFactor node: {risk.concern[:50]}")

                relationships.append(ContractRelationship(
                    type="HAS_RISK",
                    source="Contract",
                    target="RiskFactor",
                    properties={"risk_level": risk.risk_level}
                ))

            logger.info(
                f"Stored contract graph: {contract.contract_id} with "
                f"{len(companies)} companies, {len(clauses)} clauses, "
                f"{len(risk_factors)} risks"
            )

            return ContractGraph(
                contract=contract,
                companies=companies,
                clauses=clauses,
                risk_factors=risk_factors,
                relationships=relationships
            )

        except Exception as e:
            logger.error(f"Error storing contract graph: {e}")
            raise

    async def get_contract_relationships(
        self,
        contract_id: str
    ) -> Optional[ContractGraph]:
        """
        Retrieve complete contract graph with all relationships.

        Args:
            contract_id: Contract identifier

        Returns:
            ContractGraph with all nodes and relationships, or None if not found
        """
        try:
            # Single query to get all related data
            result = self.graph.query(
                """
                MATCH (c:Contract {contract_id: $contract_id})
                OPTIONAL MATCH (co:Company)-[:PARTY_TO]->(c)
                OPTIONAL MATCH (c)-[:CONTAINS]->(cl:Clause)
                OPTIONAL MATCH (c)-[:HAS_RISK]->(r:RiskFactor)
                RETURN c, collect(DISTINCT co) as companies,
                       collect(DISTINCT cl) as clauses,
                       collect(DISTINCT r) as risks
                """,
                {'contract_id': contract_id}
            )

            if not result.result_set or len(result.result_set) == 0:
                logger.warning(f"Contract not found: {contract_id}")
                return None

            row = result.result_set[0]
            contract_data = row[0]

            contract = ContractNode(
                contract_id=contract_data.properties["contract_id"],
                filename=contract_data.properties["filename"],
                upload_date=datetime.fromisoformat(contract_data.properties["upload_date"]),
                risk_score=contract_data.properties.get("risk_score"),
                risk_level=contract_data.properties.get("risk_level"),
                payment_amount=contract_data.properties.get("payment_amount"),
                payment_frequency=contract_data.properties.get("payment_frequency"),
                has_termination_clause=contract_data.properties.get("has_termination_clause"),
                liability_cap=contract_data.properties.get("liability_cap")
            )

            companies = [
                CompanyNode(**node.properties)
                for node in row[1] if node is not None
            ]

            clauses = [
                ClauseNode(
                    section_name=node.properties["section_name"],
                    content=node.properties["content"],
                    clause_type=node.properties.get("clause_type"),
                    importance=node.properties.get("importance")
                )
                for node in row[2] if node is not None
            ]

            risk_factors = [
                RiskFactorNode(
                    concern=node.properties["concern"],
                    risk_level=node.properties["risk_level"],
                    section=node.properties.get("section"),
                    recommendation=node.properties.get("recommendation")
                )
                for node in row[3] if node is not None
            ]

            logger.info(f"Retrieved contract graph: {contract_id}")

            return ContractGraph(
                contract=contract,
                companies=companies,
                clauses=clauses,
                risk_factors=risk_factors,
                relationships=[]
            )

        except Exception as e:
            logger.error(f"Error retrieving contract graph: {e}")
            raise

    async def find_similar_contracts(
        self,
        risk_level: str,
        limit: int = 5
    ) -> List[ContractNode]:
        """
        Find contracts with similar risk levels.

        Args:
            risk_level: Risk level to match (low, medium, high)
            limit: Maximum number of results

        Returns:
            List of contract nodes
        """
        try:
            result = self.graph.query(
                """
                MATCH (c:Contract {risk_level: $risk_level})
                RETURN c
                ORDER BY c.upload_date DESC
                LIMIT $limit
                """,
                {
                    'risk_level': risk_level,
                    'limit': limit
                }
            )

            contracts = [
                ContractNode(
                    contract_id=record[0].properties["contract_id"],
                    filename=record[0].properties["filename"],
                    upload_date=datetime.fromisoformat(record[0].properties["upload_date"]),
                    risk_score=record[0].properties.get("risk_score"),
                    risk_level=record[0].properties.get("risk_level")
                )
                for record in result.result_set
            ]

            return contracts

        except Exception as e:
            logger.error(f"Error finding similar contracts: {e}")
            raise

    def delete_contract(self, contract_id: str) -> bool:
        """
        Delete contract and all related nodes.

        Args:
            contract_id: Contract identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            result = self.graph.query(
                """
                MATCH (c:Contract {contract_id: $contract_id})
                OPTIONAL MATCH (c)-[r]->(n)
                DELETE r, n, c
                RETURN count(c) as deleted
                """,
                {'contract_id': contract_id}
            )

            deleted = len(result.result_set) > 0 and result.result_set[0][0] > 0

            if deleted:
                logger.info(f"Deleted contract graph: {contract_id}")
            else:
                logger.warning(f"Contract not found for deletion: {contract_id}")

            return deleted

        except Exception as e:
            logger.error(f"Error deleting contract: {e}")
            raise

    def close(self) -> None:
        """Close the FalkorDB connection."""
        if hasattr(self, 'db'):
            self.db.close()
            logger.info("FalkorDB connection closed")
