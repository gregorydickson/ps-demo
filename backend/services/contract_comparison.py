"""Contract comparison using expert legal analysis."""

import logging
from typing import List, Dict, Any, Optional

try:
    from ..services.gemini_router import GeminiRouter, LegalExpertise
    from ..services.vector_store import ContractVectorStore
    from ..services.graph_store import ContractGraphStore
except ImportError:
    from backend.services.gemini_router import GeminiRouter, LegalExpertise
    from backend.services.vector_store import ContractVectorStore
    from backend.services.graph_store import ContractGraphStore


logger = logging.getLogger(__name__)


class ContractComparisonService:
    """Compare two contracts using AI analysis."""

    def __init__(
        self,
        gemini_router: GeminiRouter,
        vector_store: ContractVectorStore,
        graph_store: ContractGraphStore
    ):
        """
        Initialize the contract comparison service.

        Args:
            gemini_router: Gemini router for AI analysis
            vector_store: ChromaDB vector store for semantic search
            graph_store: FalkorDB graph store for contract metadata
        """
        self.gemini_router = gemini_router
        self.vector_store = vector_store
        self.graph_store = graph_store

    async def compare(
        self,
        contract_id_a: str,
        contract_id_b: str,
        aspects: List[str]
    ) -> Dict[str, Any]:
        """
        Compare contracts across specified aspects.

        This method:
        1. Retrieves graph data for both contracts
        2. For each aspect, performs semantic search to find relevant sections
        3. Uses CONTRACT_REVIEWER expertise to analyze differences
        4. Returns structured comparison with cost tracking

        Args:
            contract_id_a: First contract ID
            contract_id_b: Second contract ID
            aspects: List of aspects to compare (e.g., ["payment_terms", "liability"])

        Returns:
            Dictionary with comparison results and total cost

        Raises:
            ValueError: If either contract is not found
        """
        logger.info(f"Comparing contracts {contract_id_a} and {contract_id_b} on {len(aspects)} aspects")

        # Get graph data for both contracts
        graph_a = await self.graph_store.get_contract_relationships(contract_id_a)
        graph_b = await self.graph_store.get_contract_relationships(contract_id_b)

        if not graph_a:
            raise ValueError(f"Contract {contract_id_a} not found")
        if not graph_b:
            raise ValueError(f"Contract {contract_id_b} not found")

        comparisons = []
        total_cost = 0.0

        for aspect in aspects:
            logger.debug(f"Comparing aspect: {aspect}")

            # Get relevant chunks for each contract
            chunks_a = await self.vector_store.semantic_search(
                query=aspect,
                contract_id=contract_id_a,
                n_results=3
            )
            chunks_b = await self.vector_store.semantic_search(
                query=aspect,
                contract_id=contract_id_b,
                n_results=3
            )

            # Build comparison prompt
            prompt = self._build_comparison_prompt(
                aspect=aspect,
                contract_a_name=graph_a.contract.filename,
                contract_b_name=graph_b.contract.filename,
                chunks_a=chunks_a,
                chunks_b=chunks_b
            )

            # Use CONTRACT_REVIEWER expertise for comparison
            result = await self.gemini_router.generate_with_expertise(
                prompt=prompt,
                expertise=LegalExpertise.CONTRACT_REVIEWER,
            )

            comparisons.append({
                "aspect": aspect,
                "analysis": result.text,
                "cost": result.cost
            })
            total_cost += result.cost

            logger.debug(f"Aspect '{aspect}' analyzed (cost: ${result.cost:.6f})")

        logger.info(
            f"Comparison complete: {len(aspects)} aspects analyzed "
            f"(total cost: ${total_cost:.6f})"
        )

        return {
            "contract_a": {
                "id": contract_id_a,
                "filename": graph_a.contract.filename
            },
            "contract_b": {
                "id": contract_id_b,
                "filename": graph_b.contract.filename
            },
            "comparisons": comparisons,
            "total_cost": total_cost
        }

    def _build_comparison_prompt(
        self,
        aspect: str,
        contract_a_name: str,
        contract_b_name: str,
        chunks_a: List[Dict[str, Any]],
        chunks_b: List[Dict[str, Any]]
    ) -> str:
        """
        Build a comparison prompt for a specific aspect.

        Args:
            aspect: The aspect to compare (e.g., "payment_terms")
            contract_a_name: Filename of first contract
            contract_b_name: Filename of second contract
            chunks_a: Relevant sections from first contract
            chunks_b: Relevant sections from second contract

        Returns:
            Formatted prompt string
        """
        # Extract text from chunks (limit to 500 chars each for context)
        context_a = "\n\n".join([
            f"Section {i+1}:\n{chunk['text'][:500]}"
            for i, chunk in enumerate(chunks_a)
        ])

        context_b = "\n\n".join([
            f"Section {i+1}:\n{chunk['text'][:500]}"
            for i, chunk in enumerate(chunks_b)
        ])

        # Handle empty contexts
        if not context_a:
            context_a = "[No relevant sections found for this aspect]"
        if not context_b:
            context_b = "[No relevant sections found for this aspect]"

        return f"""Compare these two contracts on the aspect: {aspect}

CONTRACT A ({contract_a_name}):
{context_a}

CONTRACT B ({contract_b_name}):
{context_b}

Please provide a structured comparison that includes:

1. **Summary of {aspect} in Contract A:**
   - Key provisions and terms
   - Notable clauses or conditions

2. **Summary of {aspect} in Contract B:**
   - Key provisions and terms
   - Notable clauses or conditions

3. **Key Differences:**
   - Material differences between the contracts
   - Variations in approach or structure

4. **Risk Implications:**
   - Which contract is more favorable to which party?
   - Potential risks or concerns arising from the differences

5. **Recommendation:**
   - Which contract has better terms for this aspect?
   - Suggested improvements or negotiations points

If relevant sections are not found for either contract, note this explicitly and provide guidance on what to look for in the full documents.
"""
