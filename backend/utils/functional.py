"""
Functional programming utilities.

Provides pure functions for data transformations, avoiding mutable state
and imperative loops where possible.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.

    Returns:
        Current datetime with UTC timezone

    Example:
        >>> now = utc_now()
        >>> now.tzinfo == timezone.utc
        True
    """
    return datetime.now(timezone.utc)


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """
    Format datetime as ISO 8601 string.

    Args:
        dt: Datetime to format, defaults to current UTC time

    Returns:
        ISO 8601 formatted string
    """
    if dt is None:
        dt = utc_now()
    return dt.isoformat()


def transform_contract_records(
    records: Optional[List[tuple]]
) -> List[Dict[str, Any]]:
    """
    Transform database records to contract dictionaries.

    Pure function that converts tuples from database queries into
    structured dictionaries, handling None values appropriately.

    Args:
        records: List of tuples from database query, or None

    Returns:
        List of contract dictionaries

    Example:
        >>> records = [("id-1", "file.pdf", "2025-01-01", 5.0, "medium", 2)]
        >>> transform_contract_records(records)
        [{'contract_id': 'id-1', 'filename': 'file.pdf', ...}]
    """
    if not records:
        return []

    return [
        {
            'contract_id': record[0],
            'filename': record[1],
            'upload_date': record[2],
            'risk_score': record[3],
            'risk_level': record[4],
            'party_count': record[5] if record[5] is not None else 0
        }
        for record in records
    ]


def group_search_results(results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Group ChromaDB search results by contract_id.

    Pure function that transforms flat ChromaDB query results into
    grouped results per contract, calculating best scores and
    aggregating matches.

    Args:
        results: ChromaDB query results with ids, documents, metadatas, distances

    Returns:
        List of grouped results sorted by best_score (lowest first)

    Example:
        >>> results = {"ids": [["c1", "c2"]], "documents": [["d1", "d2"]], ...}
        >>> grouped = group_search_results(results)
        >>> grouped[0]["contract_id"]
        'contract-a'
    """
    if not results.get('ids') or not results['ids'][0]:
        return []

    # Build list of (contract_id, doc, distance) tuples
    items = [
        (
            results['metadatas'][0][i].get('contract_id'),
            results['documents'][0][i],
            results['distances'][0][i]
        )
        for i in range(len(results['ids'][0]))
        if results['metadatas'][0][i].get('contract_id')
    ]

    # Group by contract_id using dict comprehension
    grouped: Dict[str, Dict[str, Any]] = {}
    for contract_id, doc, distance in items:
        if contract_id not in grouped:
            grouped[contract_id] = {
                "contract_id": contract_id,
                "matches": [],
                "best_score": float('inf')
            }

        grouped[contract_id]["matches"].append({
            "text": doc[:200],
            "score": 1 - distance
        })
        grouped[contract_id]["best_score"] = min(
            grouped[contract_id]["best_score"],
            distance
        )

    # Sort by best_score and return as list
    return sorted(
        grouped.values(),
        key=lambda x: x["best_score"]
    )


async def enrich_search_result(
    result: Dict[str, Any],
    graph_store
) -> Dict[str, Any]:
    """
    Enrich a single search result with graph store metadata.

    Async function that fetches contract details from graph store
    and merges with search result.

    Args:
        result: Search result dict with contract_id, matches, best_score
        graph_store: Graph store instance for fetching metadata

    Returns:
        Enriched result dict with filename, risk_score, etc.
    """
    contract_id = result["contract_id"]
    contract_graph = await graph_store.get_contract_relationships(contract_id)

    base = {
        "contract_id": contract_id,
        "matches": result.get("matches", []),
        "relevance_score": 1 - result["best_score"]
    }

    if contract_graph:
        return {
            **base,
            "filename": contract_graph.contract.filename,
            "upload_date": contract_graph.contract.upload_date.isoformat(),
            "risk_score": contract_graph.contract.risk_score,
            "risk_level": contract_graph.contract.risk_level,
        }

    logger.warning(f"Contract {contract_id} found in vector store but not graph store")
    return {
        **base,
        "filename": "Unknown",
        "upload_date": None,
        "risk_score": None,
        "risk_level": None
    }


async def enrich_results_parallel(
    results: List[Dict[str, Any]],
    graph_store
) -> List[Dict[str, Any]]:
    """
    Enrich multiple search results in parallel.

    Uses asyncio.gather for concurrent enrichment while preserving
    result order.

    Args:
        results: List of search results to enrich
        graph_store: Graph store instance

    Returns:
        List of enriched results in same order as input
    """
    if not results:
        return []

    enriched = await asyncio.gather(
        *[enrich_search_result(r, graph_store) for r in results]
    )
    return list(enriched)


def build_contract_summary(contract_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a contract summary from raw data.

    Pure function for transforming contract data into summary format.

    Args:
        contract_data: Raw contract data dict

    Returns:
        Contract summary dict
    """
    upload_date = contract_data.get('upload_date')
    if isinstance(upload_date, str):
        upload_date = datetime.fromisoformat(upload_date)

    return {
        'contract_id': contract_data['contract_id'],
        'filename': contract_data['filename'],
        'upload_date': upload_date,
        'risk_score': contract_data.get('risk_score'),
        'risk_level': contract_data.get('risk_level'),
        'party_count': contract_data.get('party_count', 0)
    }


def build_contract_summaries(
    contracts_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Build contract summaries from list of raw data.

    Args:
        contracts_data: List of raw contract data dicts

    Returns:
        List of contract summary dicts
    """
    return [build_contract_summary(c) for c in contracts_data]
