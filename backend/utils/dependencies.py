"""
FastAPI dependency injection for services.

Provides dependency functions for use with FastAPI's Depends() system.
This enables cleaner endpoint signatures and automatic service availability checks.
"""

from typing import Optional
from fastapi import HTTPException

# Service instances - set during app startup
_vector_store = None
_graph_store = None
_qa_workflow = None
_cost_tracker = None
_workflow = None


def set_vector_store(store) -> None:
    """Set the global vector store instance."""
    global _vector_store
    _vector_store = store


def set_graph_store(store) -> None:
    """Set the global graph store instance."""
    global _graph_store
    _graph_store = store


def set_qa_workflow(workflow) -> None:
    """Set the global QA workflow instance."""
    global _qa_workflow
    _qa_workflow = workflow


def set_cost_tracker(tracker) -> None:
    """Set the global cost tracker instance."""
    global _cost_tracker
    _cost_tracker = tracker


def set_workflow(wf) -> None:
    """Set the global workflow instance."""
    global _workflow
    _workflow = wf


def get_vector_store():
    """
    FastAPI dependency for vector store.

    Returns:
        ContractVectorStore instance

    Raises:
        HTTPException: 503 if vector store not initialized
    """
    if _vector_store is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ServiceUnavailable",
                "message": "Vector store not initialized"
            }
        )
    return _vector_store


def get_graph_store():
    """
    FastAPI dependency for graph store.

    Returns:
        ContractGraphStore instance

    Raises:
        HTTPException: 503 if graph store not initialized
    """
    if _graph_store is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ServiceUnavailable",
                "message": "Graph store not initialized"
            }
        )
    return _graph_store


def get_qa_workflow():
    """
    FastAPI dependency for QA workflow.

    Returns:
        QAWorkflow instance

    Raises:
        HTTPException: 503 if QA workflow not initialized
    """
    if _qa_workflow is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ServiceUnavailable",
                "message": "Q&A service not initialized"
            }
        )
    return _qa_workflow


def get_cost_tracker():
    """
    FastAPI dependency for cost tracker.

    Returns:
        CostTracker instance or None if not initialized
    """
    return _cost_tracker


def get_workflow():
    """
    FastAPI dependency for main workflow.

    Returns:
        Workflow instance

    Raises:
        HTTPException: 503 if workflow not initialized
    """
    if _workflow is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ServiceUnavailable",
                "message": "Workflow not initialized"
            }
        )
    return _workflow
