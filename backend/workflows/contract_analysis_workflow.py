"""
LangGraph workflow for legal contract analysis.

Orchestrates document parsing, risk analysis, storage, and Q&A in a
sequential agentic workflow with proper state management and error handling.
"""

import logging
import json
from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime

from langgraph.graph import StateGraph, END
import google.generativeai as genai

# Import services (these will be from Part 1)
# Note: These imports will work once Part 1 is complete
try:
    from ..services.gemini_router import GeminiRouter, LegalExpertise
    from ..services.llamaparse_service import LlamaParseService
except ImportError:
    # Placeholder for development - will be replaced with actual imports
    GeminiRouter = None
    LlamaParseService = None
    LegalExpertise = None

from ..services.vector_store import ContractVectorStore
from ..services.graph_store import ContractGraphStore
from ..models.graph_schemas import (
    ContractNode,
    CompanyNode,
    ClauseNode,
    RiskFactorNode
)

logger = logging.getLogger(__name__)


# Define state schema for the workflow
class ContractAnalysisState(TypedDict, total=False):
    """
    State schema for contract analysis workflow.

    Input fields:
        contract_id: Unique identifier for the contract
        file_bytes: Raw file data
        filename: Original filename
        query: Optional user query for Q&A

    Intermediate fields:
        parsed_document: Parsed text from LlamaParse
        risk_analysis: Risk analysis results from Gemini
        key_terms: Extracted key terms from analysis

    Output fields:
        vector_ids: List of stored vector IDs
        graph_stored: Boolean indicating graph storage success
        answer: Answer to user query (if provided)
        total_cost: Accumulated API costs
        errors: List of error messages
    """
    # Input
    contract_id: str
    file_bytes: bytes
    filename: str
    query: Optional[str]

    # Intermediate state
    parsed_document: Optional[str]
    risk_analysis: Optional[Dict[str, Any]]
    key_terms: Optional[Dict[str, Any]]

    # Output
    vector_ids: Optional[List[str]]
    graph_stored: Optional[bool]
    answer: Optional[str]
    total_cost: Optional[float]
    errors: Optional[List[str]]


class ContractAnalysisWorkflow:
    """
    LangGraph workflow for contract analysis pipeline.

    Nodes:
    1. parse_document - Extract text using LlamaParse
    2. analyze_risk - Analyze risks using Gemini Flash
    3. store_vectors - Store in ChromaDB
    4. store_graph - Store in Neo4j
    5. qa - Answer questions using semantic search
    """

    def __init__(self, initialize_stores: bool = True):
        """
        Initialize workflow with required services.

        Args:
            initialize_stores: Whether to initialize stores immediately.
                               Set to False for testing without services running.
        """
        # Initialize services
        self.gemini_router = GeminiRouter() if GeminiRouter else None
        self.llamaparse = LlamaParseService() if LlamaParseService else None

        # Lazy initialization of stores
        if initialize_stores:
            self.vector_store = ContractVectorStore()
            self.graph_store = ContractGraphStore()
        else:
            self.vector_store = None
            self.graph_store = None

        # Build workflow graph
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow with sequential node execution.

        Flow: parse → analyze → store_vectors → store_graph → qa → END
        """
        # Create graph
        workflow = StateGraph(ContractAnalysisState)

        # Add nodes
        workflow.add_node("parse", self._parse_document_node)
        workflow.add_node("analyze", self._analyze_risk_node)
        workflow.add_node("store_vectors", self._store_vectors_node)
        workflow.add_node("store_graph", self._store_graph_node)
        workflow.add_node("qa", self._qa_node)

        # Define edges (sequential flow)
        workflow.set_entry_point("parse")
        workflow.add_edge("parse", "analyze")
        workflow.add_edge("analyze", "store_vectors")
        workflow.add_edge("store_vectors", "store_graph")
        workflow.add_edge("store_graph", "qa")
        workflow.add_edge("qa", END)

        return workflow.compile()

    async def _parse_document_node(
        self,
        state: ContractAnalysisState
    ) -> ContractAnalysisState:
        """
        Node 1: Parse document using LlamaParse.

        Args:
            state: Current workflow state

        Returns:
            Updated state with parsed_document
        """
        logger.info(f"[parse_document] Processing {state['filename']}")

        try:
            if not self.llamaparse:
                # Fallback for testing without Part 1
                state["parsed_document"] = "Mock parsed document content"
                state["errors"] = state.get("errors", [])
                state["errors"].append("LlamaParse service not available - using mock data")
                logger.warning("Using mock parsed document")
            else:
                # Use actual LlamaParse service
                parsed_text = await self.llamaparse.parse_document(
                    file_bytes=state["file_bytes"],
                    filename=state["filename"]
                )
                state["parsed_document"] = parsed_text

            logger.info(
                f"[parse_document] Parsed {len(state.get('parsed_document', ''))} characters"
            )

        except Exception as e:
            error_msg = f"Parse error: {str(e)}"
            logger.error(f"[parse_document] {error_msg}")
            state["errors"] = state.get("errors", [])
            state["errors"].append(error_msg)
            state["parsed_document"] = ""

        return state

    async def _analyze_risk_node(
        self,
        state: ContractAnalysisState
    ) -> ContractAnalysisState:
        """
        Node 2: Analyze contract risks using Gemini Flash.

        Args:
            state: Current workflow state

        Returns:
            Updated state with risk_analysis and key_terms
        """
        logger.info("[analyze_risk] Analyzing contract risks")

        if not state.get("parsed_document"):
            logger.warning("[analyze_risk] No parsed document available")
            state["risk_analysis"] = {}
            state["key_terms"] = {}
            return state

        try:
            # Build risk analysis prompt
            prompt = self._build_risk_analysis_prompt(state["parsed_document"])

            if not self.gemini_router:
                # Fallback for testing without Part 1
                state["risk_analysis"] = {
                    "risk_score": 5.0,
                    "risk_level": "medium",
                    "concerning_clauses": []
                }
                state["key_terms"] = {
                    "payment_amount": "unknown",
                    "payment_frequency": "unknown",
                    "termination_clause": False,
                    "liability_cap": "unknown"
                }
                state["errors"] = state.get("errors", [])
                state["errors"].append("GeminiRouter not available - using mock data")
                logger.warning("Using mock risk analysis")
            else:
                # Use actual Gemini router with expert legal persona
                response = await self.gemini_router.generate_with_expertise(
                    prompt=prompt,
                    expertise=LegalExpertise.RISK_ANALYST,
                    additional_context=f"Contract: {state['filename']}"
                )

                # Parse JSON response
                analysis = json.loads(response.text)
                state["risk_analysis"] = analysis
                state["key_terms"] = analysis.get("key_terms", {})

                # Update cost tracking
                state["total_cost"] = state.get("total_cost", 0.0) + response.cost

            logger.info(
                f"[analyze_risk] Risk score: {state['risk_analysis'].get('risk_score')}, "
                f"Level: {state['risk_analysis'].get('risk_level')}"
            )

        except Exception as e:
            error_msg = f"Risk analysis error: {str(e)}"
            logger.error(f"[analyze_risk] {error_msg}")
            state["errors"] = state.get("errors", [])
            state["errors"].append(error_msg)
            state["risk_analysis"] = {}
            state["key_terms"] = {}

        return state

    async def _store_vectors_node(
        self,
        state: ContractAnalysisState
    ) -> ContractAnalysisState:
        """
        Node 3: Store document in ChromaDB vector store.

        Args:
            state: Current workflow state

        Returns:
            Updated state with vector_ids
        """
        logger.info("[store_vectors] Storing document in vector store")

        if not state.get("parsed_document"):
            logger.warning("[store_vectors] No parsed document to store")
            state["vector_ids"] = []
            return state

        try:
            # Prepare metadata
            metadata = {
                "filename": state["filename"],
                "upload_date": datetime.now().isoformat(),
                "risk_level": state.get("risk_analysis", {}).get("risk_level", "unknown")
            }

            # Store in vector database
            vector_ids = await self.vector_store.store_document_sections(
                contract_id=state["contract_id"],
                document_text=state["parsed_document"],
                metadata=metadata
            )

            state["vector_ids"] = vector_ids

            logger.info(f"[store_vectors] Stored {len(vector_ids)} chunks")

        except Exception as e:
            error_msg = f"Vector storage error: {str(e)}"
            logger.error(f"[store_vectors] {error_msg}")
            state["errors"] = state.get("errors", [])
            state["errors"].append(error_msg)
            state["vector_ids"] = []

        return state

    async def _store_graph_node(
        self,
        state: ContractAnalysisState
    ) -> ContractAnalysisState:
        """
        Node 4: Store contract graph in Neo4j.

        Args:
            state: Current workflow state

        Returns:
            Updated state with graph_stored flag
        """
        logger.info("[store_graph] Storing contract graph")

        try:
            risk_analysis = state.get("risk_analysis", {})
            key_terms = state.get("key_terms", {})

            # Create contract node
            contract = ContractNode(
                contract_id=state["contract_id"],
                filename=state["filename"],
                upload_date=datetime.now(),
                risk_score=risk_analysis.get("risk_score"),
                risk_level=risk_analysis.get("risk_level"),
                payment_amount=key_terms.get("payment_amount"),
                payment_frequency=key_terms.get("payment_frequency"),
                has_termination_clause=key_terms.get("termination_clause"),
                liability_cap=key_terms.get("liability_cap")
            )

            # Extract companies (if available in risk analysis)
            companies = self._extract_companies(risk_analysis)

            # Extract clauses
            clauses = self._extract_clauses(risk_analysis)

            # Extract risk factors
            risk_factors = self._extract_risk_factors(risk_analysis)

            # Store in graph database
            await self.graph_store.store_contract(
                contract=contract,
                companies=companies,
                clauses=clauses,
                risk_factors=risk_factors
            )

            state["graph_stored"] = True

            logger.info("[store_graph] Successfully stored contract graph")

        except Exception as e:
            error_msg = f"Graph storage error: {str(e)}"
            logger.error(f"[store_graph] {error_msg}")
            state["errors"] = state.get("errors", [])
            state["errors"].append(error_msg)
            state["graph_stored"] = False

        return state

    async def _qa_node(
        self,
        state: ContractAnalysisState
    ) -> ContractAnalysisState:
        """
        Node 5: Answer user query using semantic search and Gemini Flash-Lite.

        Args:
            state: Current workflow state

        Returns:
            Updated state with answer
        """
        logger.info("[qa] Processing user query")

        # Skip if no query provided
        if not state.get("query"):
            logger.info("[qa] No query provided, skipping")
            state["answer"] = None
            return state

        try:
            # Perform semantic search
            search_results = await self.vector_store.semantic_search(
                query=state["query"],
                n_results=3,
                contract_id=state["contract_id"]
            )

            # Build context from search results
            context = "\n\n".join([
                f"Section {i+1}:\n{result['text']}"
                for i, result in enumerate(search_results)
            ])

            # Generate answer using Gemini
            qa_prompt = f"""Based on the following contract sections, answer the user's question.

CONTRACT SECTIONS:
{context}

USER QUESTION:
{state['query']}

Provide a clear, concise answer based only on the information in the contract sections above.
If the information is not available, say so."""

            if not self.gemini_router:
                # Fallback for testing
                state["answer"] = f"Mock answer to: {state['query']}"
                logger.warning("Using mock answer")
            else:
                # Use actual Gemini router with Q&A expert persona
                response = await self.gemini_router.generate_with_expertise(
                    prompt=qa_prompt,
                    expertise=LegalExpertise.QA_ASSISTANT
                )

                state["answer"] = response.text

                # Update cost tracking
                state["total_cost"] = state.get("total_cost", 0.0) + response.cost

            logger.info(f"[qa] Generated answer ({len(state.get('answer', ''))} chars)")

        except Exception as e:
            error_msg = f"Q&A error: {str(e)}"
            logger.error(f"[qa] {error_msg}")
            state["errors"] = state.get("errors", [])
            state["errors"].append(error_msg)
            state["answer"] = "Error generating answer"

        return state

    def _build_risk_analysis_prompt(self, parsed_text: str) -> str:
        """Build prompt for risk analysis."""
        return f"""Analyze this legal contract for risk factors.

CONTRACT TEXT:
{parsed_text[:10000]}

Provide analysis in JSON format:
{{
    "risk_score": <0-10>,
    "risk_level": "low|medium|high",
    "concerning_clauses": [
        {{
            "section": "section name",
            "concern": "description",
            "risk_level": "low|medium|high",
            "recommendation": "suggestion"
        }}
    ],
    "key_terms": {{
        "payment_amount": "amount",
        "payment_frequency": "frequency",
        "termination_clause": true/false,
        "liability_cap": "amount or unlimited"
    }}
}}"""

    def _extract_companies(self, risk_analysis: Dict[str, Any]) -> List[CompanyNode]:
        """Extract company nodes from risk analysis."""
        # This is a placeholder - in production you'd parse the document
        # to extract actual party information
        return [
            CompanyNode(name="Unknown Party A", role="party_a"),
            CompanyNode(name="Unknown Party B", role="party_b")
        ]

    def _extract_clauses(self, risk_analysis: Dict[str, Any]) -> List[ClauseNode]:
        """Extract clause nodes from risk analysis."""
        clauses = []

        for concern in risk_analysis.get("concerning_clauses", []):
            clauses.append(ClauseNode(
                section_name=concern.get("section", "Unknown"),
                content=concern.get("concern", ""),
                clause_type="concern",
                importance="high" if concern.get("risk_level") == "high" else "medium"
            ))

        return clauses

    def _extract_risk_factors(
        self,
        risk_analysis: Dict[str, Any]
    ) -> List[RiskFactorNode]:
        """Extract risk factor nodes from risk analysis."""
        risk_factors = []

        for concern in risk_analysis.get("concerning_clauses", []):
            risk_factors.append(RiskFactorNode(
                concern=concern.get("concern", ""),
                risk_level=concern.get("risk_level", "medium"),
                section=concern.get("section"),
                recommendation=concern.get("recommendation")
            ))

        return risk_factors

    async def run(
        self,
        contract_id: str,
        file_bytes: bytes,
        filename: str,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute the contract analysis workflow.

        Args:
            contract_id: Unique contract identifier
            file_bytes: Raw file data
            filename: Original filename
            query: Optional user query for Q&A

        Returns:
            Final workflow state as dictionary
        """
        # Initialize state
        initial_state: ContractAnalysisState = {
            "contract_id": contract_id,
            "file_bytes": file_bytes,
            "filename": filename,
            "query": query,
            "errors": [],
            "total_cost": 0.0
        }

        logger.info(f"Starting workflow for contract: {contract_id}")

        try:
            # Run workflow
            final_state = await self.workflow.ainvoke(initial_state)

            logger.info(
                f"Workflow completed for {contract_id}. "
                f"Cost: ${final_state.get('total_cost', 0):.4f}, "
                f"Errors: {len(final_state.get('errors', []))}"
            )

            return final_state

        except Exception as e:
            logger.error(f"Workflow error for {contract_id}: {e}")
            initial_state["errors"].append(f"Workflow error: {str(e)}")
            return initial_state


# Create singleton workflow instance (with lazy initialization)
# Services will be initialized on first use
contract_workflow = None


def get_workflow(initialize_stores: bool = True) -> ContractAnalysisWorkflow:
    """
    Get or create the workflow instance.

    Args:
        initialize_stores: Whether to initialize stores (requires services running)

    Returns:
        ContractAnalysisWorkflow instance
    """
    global contract_workflow
    if contract_workflow is None:
        contract_workflow = ContractAnalysisWorkflow(initialize_stores=initialize_stores)
    return contract_workflow
