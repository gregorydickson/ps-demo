"""
Services package for Legal Contract Intelligence Platform.

Core services for document parsing, AI generation, and cost tracking.
"""

# Part 1 services (optional imports - will be available once Part 1 is complete)
try:
    from .gemini_router import GeminiRouter, TaskComplexity, GenerationResult
    from .cost_tracker import CostTracker
    from .llamaparse_service import LegalDocumentParser
    _part1_available = True
except ImportError:
    GeminiRouter = None
    TaskComplexity = None
    GenerationResult = None
    CostTracker = None
    LegalDocumentParser = None
    _part1_available = False

# Part 2 services (optional imports - will be available once dependencies are installed)
try:
    from .vector_store import ContractVectorStore
    from .graph_store import ContractGraphStore
    _part2_available = True
except ImportError:
    ContractVectorStore = None
    ContractGraphStore = None
    _part2_available = False

__all__ = [
    # Part 1
    "GeminiRouter",
    "TaskComplexity",
    "GenerationResult",
    "CostTracker",
    "LegalDocumentParser",
    # Part 2
    "ContractVectorStore",
    "ContractGraphStore",
]
