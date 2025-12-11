"""
FastAPI REST API for Legal Contract Intelligence Platform.

Provides endpoints for:
- Contract upload and analysis
- Contract querying (Q&A)
- Contract details retrieval
- Cost analytics
"""

import os
import logging
import time
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Literal

from fastapi import FastAPI, UploadFile, File, HTTPException, Path, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Import services
try:
    # Try relative imports first (when run as module)
    from .services.cost_tracker import CostTracker
    from .services.graph_store import ContractGraphStore
    from .services.vector_store import ContractVectorStore
    from .workflows.contract_analysis_workflow import get_workflow as get_analysis_workflow
    from .workflows.qa_workflow import QAWorkflow
    from .utils.request_context import set_request_id, clear_request_context
    from .utils.decorators import handle_endpoint_errors
    from .utils.dependencies import (
        set_vector_store, set_graph_store, set_qa_workflow,
        set_cost_tracker, set_workflow,
        get_vector_store, get_graph_store, get_qa_workflow,
        get_cost_tracker, get_workflow
    )
    from .utils.functional import (
        utc_now, format_timestamp, enrich_results_parallel,
        build_contract_summaries
    )
    from .models.schemas import (
        ContractAnalysisResponse,
        ContractQueryRequest,
        ContractQueryResponse,
        ContractDetailsResponse,
        ContractSummary,
        ContractListResponse,
        ContractComparisonRequest,
        ContractComparisonResponse,
        CostAnalytics,
        ErrorResponse,
        BatchUploadResult,
        BatchUploadResponse,
        GlobalSearchResponse
    )
except ImportError:
    # Fall back to absolute imports (when run directly)
    from backend.services.cost_tracker import CostTracker
    from backend.services.graph_store import ContractGraphStore
    from backend.services.vector_store import ContractVectorStore
    from backend.workflows.contract_analysis_workflow import get_workflow as get_analysis_workflow
    from backend.workflows.qa_workflow import QAWorkflow
    from backend.utils.request_context import set_request_id, clear_request_context
    from backend.utils.decorators import handle_endpoint_errors
    from backend.utils.dependencies import (
        set_vector_store, set_graph_store, set_qa_workflow,
        set_cost_tracker, set_workflow,
        get_vector_store, get_graph_store, get_qa_workflow,
        get_cost_tracker, get_workflow
    )
    from backend.utils.functional import (
        utc_now, format_timestamp, enrich_results_parallel,
        build_contract_summaries
    )
    from backend.models.schemas import (
        ContractAnalysisResponse,
        ContractQueryRequest,
        ContractQueryResponse,
        ContractDetailsResponse,
        ContractSummary,
        ContractListResponse,
        ContractComparisonRequest,
        ContractComparisonResponse,
        CostAnalytics,
        ErrorResponse,
        BatchUploadResult,
        BatchUploadResponse,
        GlobalSearchResponse
    )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Request Context Middleware
class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to set request ID for each request."""

    async def dispatch(self, request, call_next):
        # Get request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID")
        request_id = set_request_id(request_id)

        # Add to request state for access in handlers
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            clear_request_context()


# Create FastAPI application
app = FastAPI(
    title="Contract Intelligence API",
    description="AI-powered legal contract analysis and risk assessment platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware (development - allow all origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Request Context middleware
app.add_middleware(RequestContextMiddleware)

# Local service references for shutdown
_local_graph_store: Optional[ContractGraphStore] = None


@app.on_event("startup")
async def startup_event():
    """
    Initialize services on application startup.

    Uses dependency injection to make services available via Depends().
    """
    global _local_graph_store

    logger.info("Starting Contract Intelligence API...")

    try:
        # Initialize CostTracker
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        cost_tracker = CostTracker(redis_url=redis_url)
        set_cost_tracker(cost_tracker)
        logger.info(f"CostTracker initialized with Redis at {redis_url}")

        # Initialize ContractGraphStore
        graph_store = ContractGraphStore()
        set_graph_store(graph_store)
        _local_graph_store = graph_store
        logger.info("ContractGraphStore initialized with FalkorDB")

        # Initialize ContractVectorStore
        vector_store = ContractVectorStore()
        set_vector_store(vector_store)
        logger.info("ContractVectorStore initialized with ChromaDB")

        # Initialize workflow
        workflow = get_analysis_workflow(initialize_stores=True)
        set_workflow(workflow)
        logger.info("Contract analysis workflow initialized")

        # Initialize QA workflow
        qa_workflow = QAWorkflow(cost_tracker=cost_tracker)
        set_qa_workflow(qa_workflow)
        logger.info("QA workflow initialized")

        logger.info("All services initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup on application shutdown.
    """
    logger.info("Shutting down Contract Intelligence API...")

    if _local_graph_store:
        _local_graph_store.close()
        logger.info("FalkorDB connection closed")

    logger.info("Shutdown complete")


@app.get("/", tags=["Health"])
async def root():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "service": "Contract Intelligence API",
        "version": "1.0.0",
        "timestamp": format_timestamp()
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Detailed health check including service status.
    """
    cost_tracker = get_cost_tracker()
    graph_store_available = True
    workflow_available = True

    try:
        get_graph_store()
    except HTTPException:
        graph_store_available = False

    try:
        get_workflow()
    except HTTPException:
        workflow_available = False

    redis_healthy = cost_tracker.health_check() if cost_tracker else False

    return {
        "status": "healthy" if redis_healthy else "degraded",
        "services": {
            "redis": "up" if redis_healthy else "down",
            "falkordb": "up" if graph_store_available else "down",
            "workflow": "up" if workflow_available else "down"
        },
        "timestamp": format_timestamp()
    }


@app.post(
    "/api/contracts/upload",
    response_model=ContractAnalysisResponse,
    tags=["Contracts"],
    status_code=201
)
async def upload_contract(
    file: UploadFile = File(..., description="PDF contract file to analyze")
):
    """
    Upload and analyze a legal contract PDF.

    This endpoint:
    1. Validates the file is a PDF
    2. Parses the document using LlamaParse
    3. Analyzes risks using Gemini
    4. Stores in ChromaDB and Neo4j
    5. Returns analysis results

    Returns:
        ContractAnalysisResponse with risk analysis, key terms, and costs

    Raises:
        400: Invalid file type (not a PDF)
        500: Processing error
    """
    start_time = time.time()

    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "InvalidFileType",
                "message": "Only PDF files are supported",
                "filename": file.filename
            }
        )

    logger.info(f"Received contract upload: {file.filename}")

    try:
        # Generate contract ID
        contract_id = str(uuid.uuid4())

        # Read file bytes
        file_bytes = await file.read()

        logger.info(f"Processing contract {contract_id} ({len(file_bytes)} bytes)")

        # Run workflow
        result = await workflow.run(
            contract_id=contract_id,
            file_bytes=file_bytes,
            filename=file.filename,
            query=None  # No query for upload
        )

        # Track cost
        if cost_tracker and result.get("total_cost"):
            # Note: Individual API calls are tracked within the workflow
            # This is just logging the total
            logger.info(f"Total cost for contract {contract_id}: ${result['total_cost']:.6f}")

        processing_time = (time.time() - start_time) * 1000  # Convert to ms

        # Build response
        response = ContractAnalysisResponse(
            contract_id=contract_id,
            filename=file.filename,
            risk_analysis=result.get("risk_analysis"),
            key_terms=result.get("key_terms"),
            total_cost=result.get("total_cost", 0.0),
            errors=result.get("errors", []),
            processing_time_ms=processing_time
        )

        logger.info(
            f"Contract {contract_id} processed successfully in {processing_time:.0f}ms"
        )

        return response

    except Exception as e:
        logger.error(f"Error processing contract upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ProcessingError",
                "message": "Failed to process contract",
                "details": str(e)
            }
        )


@app.post(
    "/api/contracts/batch-upload",
    response_model=BatchUploadResponse,
    tags=["Contracts"],
    status_code=201
)
async def batch_upload_contracts(
    files: List[UploadFile] = File(..., description="PDF files (max 5)")
):
    """
    Upload and analyze multiple contracts concurrently.

    This endpoint:
    1. Validates all files are PDFs
    2. Processes up to 5 files concurrently
    3. Returns individual results for each file
    4. Continues processing even if some files fail

    Args:
        files: List of PDF contract files to analyze (max 5)

    Returns:
        BatchUploadResponse with individual results and aggregate statistics

    Raises:
        400: Too many files (>5) or invalid file types
        500: Processing error
    """
    start_time = time.time()

    # Validate maximum file count
    if len(files) > 5:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "TooManyFiles",
                "message": "Maximum 5 files per batch upload",
                "provided": len(files)
            }
        )

    # Validate all files are PDFs
    for file in files:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "InvalidFileType",
                    "message": f"All files must be PDFs. Invalid file: {file.filename}",
                    "filename": file.filename
                }
            )

    logger.info(f"Batch upload started with {len(files)} files")

    async def process_one_file(file: UploadFile) -> BatchUploadResult:
        """Process a single file and return its result."""
        try:
            # Generate contract ID
            contract_id = str(uuid.uuid4())

            # Read file bytes
            file_bytes = await file.read()

            logger.info(f"Processing {file.filename} (contract {contract_id})")

            # Run workflow
            result = await workflow.run(
                contract_id=contract_id,
                file_bytes=file_bytes,
                filename=file.filename,
                query=None  # No query for upload
            )

            # Extract risk level
            risk_level = None
            if result.get("risk_analysis"):
                risk_level = result["risk_analysis"].get("risk_level")

            logger.info(f"Successfully processed {file.filename} (risk: {risk_level})")

            return BatchUploadResult(
                filename=file.filename,
                contract_id=contract_id,
                status="success",
                risk_level=risk_level
            )

        except Exception as e:
            logger.error(f"Failed to process {file.filename}: {e}", exc_info=True)
            return BatchUploadResult(
                filename=file.filename,
                status="failed",
                error=str(e)
            )

    # Process all files concurrently
    results = await asyncio.gather(*[process_one_file(f) for f in files])

    # Calculate aggregate statistics
    successful = sum(1 for r in results if r.status == "success")
    failed = len(files) - successful
    processing_time = (time.time() - start_time) * 1000  # Convert to ms

    # Calculate total cost from cost tracker
    # Note: Individual API calls are already tracked within the workflow
    # This would ideally sum up costs from the results, but since we don't
    # return cost per file, we'll set it to 0.0 for now
    total_cost = 0.0

    response = BatchUploadResponse(
        total=len(files),
        successful=successful,
        failed=failed,
        results=results,
        total_cost=total_cost,
        processing_time_ms=processing_time
    )

    logger.info(
        f"Batch upload completed: {successful}/{len(files)} successful "
        f"in {processing_time:.0f}ms"
    )

    return response


@app.post(
    "/api/contracts/{contract_id}/query",
    response_model=ContractQueryResponse,
    tags=["Contracts"]
)
async def query_contract(
    contract_id: str = Path(..., description="Contract identifier"),
    request: ContractQueryRequest = ...
):
    """
    Ask a question about a specific contract.

    Uses lightweight Q&A workflow for efficient querying:
    1. Semantic search on ChromaDB to find relevant sections
    2. Answer generation using Gemini Flash-Lite

    This is much more efficient than running the full analysis workflow.

    Args:
        contract_id: The contract to query
        request: Query request with the question

    Returns:
        ContractQueryResponse with the answer and cost

    Raises:
        404: Contract not found
        503: Q&A service not initialized
        500: Query processing error
    """
    logger.info(f"Query for contract {contract_id}: {request.query}")

    if not qa_workflow:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ServiceUnavailable",
                "message": "Q&A service not initialized"
            }
        )

    try:
        # Verify contract exists in graph store
        contract_exists = await graph_store.get_contract_relationships(contract_id)
        if not contract_exists:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "ContractNotFound",
                    "message": f"Contract {contract_id} not found"
                }
            )

        # Run lightweight Q&A workflow
        result = await qa_workflow.run(
            contract_id=contract_id,
            query=request.query
        )

        if result["error"]:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "QueryError",
                    "message": result["error"]
                }
            )

        response = ContractQueryResponse(
            contract_id=contract_id,
            query=request.query,
            answer=result["answer"],
            cost=result["cost"],
            relevant_sections=len(result["context_chunks"])
        )

        logger.info(
            f"Query answered for contract {contract_id} "
            f"(cost: ${result['cost']:.6f})"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "QueryError",
                "message": "Failed to process query",
                "details": str(e)
            }
        )


@app.get(
    "/api/contracts/search",
    response_model=GlobalSearchResponse,
    tags=["Contracts"]
)
@handle_endpoint_errors("SearchError")
async def search_contracts(
    query: str = Query(
        ...,
        min_length=3,
        description="Search query (minimum 3 characters)"
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of contracts to return (1-50)"
    ),
    risk_level: Optional[Literal["low", "medium", "high"]] = Query(
        None,
        description="Filter by risk level"
    ),
    vector_store=Depends(get_vector_store),
    graph_store=Depends(get_graph_store)
):
    """
    Search across ALL contracts using semantic search.

    This endpoint:
    1. Performs vector search across all contract embeddings
    2. Groups results by contract_id
    3. Enriches results with contract metadata from graph store (in parallel)
    4. Returns top matching contracts

    Args:
        query: Natural language search query
        limit: Maximum number of contracts to return
        risk_level: Optional filter by risk level
        vector_store: Injected vector store dependency
        graph_store: Injected graph store dependency

    Returns:
        GlobalSearchResponse with matching contracts and their details

    Raises:
        422: Invalid query parameters (via Literal type validation)
        503: Store not initialized
        500: Search error
    """
    logger.info(f"Global search: '{query}' (limit={limit}, risk_level={risk_level})")

    # Perform global search
    search_results = await vector_store.global_search(
        query=query,
        n_results=limit * 3,  # Get more results for better grouping
        risk_level=risk_level
    )

    # Enrich results with graph data using parallel async operations
    enriched_results = await enrich_results_parallel(
        search_results[:limit],
        graph_store
    )

    response = GlobalSearchResponse(
        query=query,
        results=enriched_results,
        total=len(enriched_results)
    )

    logger.info(f"Global search returned {len(enriched_results)} contracts")

    return response


@app.get(
    "/api/contracts",
    response_model=ContractListResponse,
    tags=["Contracts"]
)
@handle_endpoint_errors("RetrievalError")
async def list_contracts(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page (max 100)"),
    risk_level: Optional[Literal["low", "medium", "high"]] = Query(
        None, description="Filter by risk level"
    ),
    sort_by: Literal["upload_date", "risk_score", "filename"] = Query(
        "upload_date", description="Sort by field"
    ),
    sort_order: Literal["asc", "desc"] = Query(
        "desc", description="Sort order"
    ),
    graph_store=Depends(get_graph_store)
):
    """
    List all contracts with pagination, filtering, and sorting.

    Supports:
    - Pagination (page, page_size)
    - Filtering by risk_level
    - Sorting by upload_date, risk_score, or filename
    - Sort order (ascending or descending)

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        risk_level: Optional filter by risk level
        sort_by: Field to sort by
        sort_order: Sort direction (asc/desc)
        graph_store: Injected graph store dependency

    Returns:
        ContractListResponse with paginated contract summaries

    Raises:
        422: Invalid query parameters (via Literal type validation)
        503: Graph store not available
        500: Retrieval error
    """
    logger.info(
        f"Listing contracts: page={page}, page_size={page_size}, "
        f"risk_level={risk_level}, sort_by={sort_by}, sort_order={sort_order}"
    )

    # Calculate skip offset (page is 1-indexed)
    skip = (page - 1) * page_size

    # Get contracts from graph store
    contracts_data, total = await graph_store.list_contracts(
        skip=skip,
        limit=page_size,
        risk_level=risk_level,
        sort_by=sort_by,
        sort_order=sort_order
    )

    # Convert to ContractSummary objects using list comprehension
    contracts = [
        ContractSummary(
            contract_id=c['contract_id'],
            filename=c['filename'],
            upload_date=datetime.fromisoformat(c['upload_date']) if isinstance(c['upload_date'], str) else c['upload_date'],
            risk_score=c['risk_score'],
            risk_level=c['risk_level'],
            party_count=c['party_count']
        )
        for c in contracts_data
    ]

    # Calculate if there are more pages
    has_more = (skip + page_size) < total

    response = ContractListResponse(
        contracts=contracts,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more
    )

    logger.info(
        f"Listed {len(contracts)} contracts (total: {total}, page: {page}/{((total - 1) // page_size) + 1 if total > 0 else 0})"
    )

    return response


@app.get(
    "/api/contracts/{contract_id}",
    response_model=ContractDetailsResponse,
    tags=["Contracts"]
)
async def get_contract_details(
    contract_id: str = Path(..., description="Contract identifier")
):
    """
    Retrieve full contract details from Neo4j graph store.

    Returns the complete graph structure including:
    - Contract metadata
    - Company/party information
    - Clauses
    - Risk factors

    Args:
        contract_id: The contract to retrieve

    Returns:
        ContractDetailsResponse with full graph data

    Raises:
        404: Contract not found
        500: Retrieval error
    """
    logger.info(f"Retrieving contract details: {contract_id}")

    try:
        # Retrieve from Neo4j
        contract_graph = await graph_store.get_contract_relationships(contract_id)

        if not contract_graph:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "ContractNotFound",
                    "message": f"Contract {contract_id} not found in graph store"
                }
            )

        # Convert to response format
        response = ContractDetailsResponse(
            contract_id=contract_graph.contract.contract_id,
            filename=contract_graph.contract.filename,
            upload_date=contract_graph.contract.upload_date,
            risk_score=contract_graph.contract.risk_score,
            risk_level=contract_graph.contract.risk_level,
            companies=[
                {
                    "name": company.name,
                    "role": company.role,
                    "company_id": company.company_id
                }
                for company in contract_graph.companies
            ],
            clauses=[
                {
                    "section_name": clause.section_name,
                    "content": clause.content,
                    "clause_type": clause.clause_type,
                    "importance": clause.importance
                }
                for clause in contract_graph.clauses
            ],
            risk_factors=[
                {
                    "concern": risk.concern,
                    "risk_level": risk.risk_level,
                    "section": risk.section,
                    "recommendation": risk.recommendation
                }
                for risk in contract_graph.risk_factors
            ]
        )

        logger.info(f"Retrieved contract {contract_id} successfully")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "RetrievalError",
                "message": "Failed to retrieve contract details",
                "details": str(e)
            }
        )


@app.delete(
    "/api/contracts/{contract_id}",
    status_code=204,
    tags=["Contracts"]
)
@handle_endpoint_errors("DeletionError")
async def delete_contract(
    contract_id: str = Path(..., description="Contract identifier"),
    graph_store=Depends(get_graph_store),
    vector_store=Depends(get_vector_store)
):
    """
    Delete a contract and all its associated data.

    This endpoint:
    1. Verifies the contract exists in the graph store
    2. Deletes all vector embeddings from ChromaDB
    3. Deletes the contract graph from FalkorDB
    4. Returns 204 No Content on success

    Args:
        contract_id: The contract to delete
        graph_store: Injected graph store dependency
        vector_store: Injected vector store dependency

    Returns:
        204 No Content on successful deletion

    Raises:
        404: Contract not found
        503: Store not available
        500: Deletion error
    """
    logger.info(f"Deleting contract: {contract_id}")

    # Check if contract exists first
    contract_exists = await graph_store.get_contract_relationships(contract_id)
    if not contract_exists:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "ContractNotFound",
                "message": f"Contract {contract_id} not found"
            }
        )

    # Delete from vector store
    vector_deleted_count = await vector_store.delete_contract(contract_id)
    logger.info(f"Deleted {vector_deleted_count} vector chunks for contract {contract_id}")

    # Delete from graph store
    graph_deleted = await graph_store.delete_contract(contract_id)
    if not graph_deleted:
        logger.warning(f"Contract {contract_id} not found in graph store during deletion")

    logger.info(f"Successfully deleted contract {contract_id}")

    return Response(status_code=204)


@app.get(
    "/api/analytics/costs",
    tags=["Analytics"]
)
async def get_cost_analytics(
    date: Optional[str] = Query(
        None,
        description="Date in YYYY-MM-DD format (defaults to today)"
    )
):
    """
    Get cost analytics for a specific date.

    Returns daily breakdown of API costs including:
    - Total cost, tokens, and calls
    - Breakdown by Gemini model
    - Breakdown by operation type

    Args:
        date: Optional date string (YYYY-MM-DD), defaults to today

    Returns:
        Cost analytics with daily breakdown

    Raises:
        400: Invalid date format
        500: Retrieval error
    """
    logger.info(f"Retrieving cost analytics for date: {date or 'today'}")

    try:
        # Parse date if provided
        target_date = None
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "InvalidDateFormat",
                        "message": "Date must be in YYYY-MM-DD format",
                        "provided": date
                    }
                )

        # Get daily costs
        daily_costs = cost_tracker.get_daily_costs(target_date)

        logger.info(
            f"Retrieved costs for {daily_costs['date']}: "
            f"${daily_costs['total_cost']:.6f}"
        )

        return daily_costs

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving cost analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "AnalyticsError",
                "message": "Failed to retrieve cost analytics",
                "details": str(e)
            }
        )


@app.post(
    "/api/contracts/compare",
    response_model=ContractComparisonResponse,
    tags=["Contracts"]
)
async def compare_contracts(
    request: ContractComparisonRequest
):
    """
    Compare two contracts across specified aspects.

    This endpoint:
    1. Validates both contracts exist in the graph store
    2. For each aspect, retrieves relevant sections via semantic search
    3. Uses CONTRACT_REVIEWER legal expertise to analyze differences
    4. Returns structured comparison with risk implications

    Args:
        request: Comparison request with contract IDs and aspects to compare

    Returns:
        ContractComparisonResponse with detailed comparison and cost

    Raises:
        404: One or both contracts not found
        503: Required services not initialized
        500: Comparison processing error
    """
    logger.info(
        f"Comparing contracts {request.contract_id_a} and {request.contract_id_b} "
        f"on {len(request.aspects)} aspects"
    )

    if not qa_workflow:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ServiceUnavailable",
                "message": "Q&A service not initialized"
            }
        )

    try:
        # Import the comparison service
        try:
            from .services.contract_comparison import ContractComparisonService
        except ImportError:
            from backend.services.contract_comparison import ContractComparisonService

        # Verify both contracts exist
        contract_a = await graph_store.get_contract_relationships(request.contract_id_a)
        contract_b = await graph_store.get_contract_relationships(request.contract_id_b)

        if not contract_a:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "ContractNotFound",
                    "message": f"Contract {request.contract_id_a} not found"
                }
            )

        if not contract_b:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "ContractNotFound",
                    "message": f"Contract {request.contract_id_b} not found"
                }
            )

        # Check vector store is initialized
        if not vector_store:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "ServiceUnavailable",
                    "message": "Vector store not initialized"
                }
            )

        # Initialize comparison service using global vector_store
        comparison_service = ContractComparisonService(
            gemini_router=qa_workflow.gemini_router,
            vector_store=vector_store,
            graph_store=graph_store
        )

        # Perform comparison
        result = await comparison_service.compare(
            contract_id_a=request.contract_id_a,
            contract_id_b=request.contract_id_b,
            aspects=request.aspects
        )

        # Track cost
        if cost_tracker and result.get("total_cost"):
            logger.info(
                f"Comparison cost for {request.contract_id_a} vs {request.contract_id_b}: "
                f"${result['total_cost']:.6f}"
            )

        logger.info(
            f"Comparison complete: {len(request.aspects)} aspects analyzed "
            f"(cost: ${result['total_cost']:.6f})"
        )

        return ContractComparisonResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        # Handle contract not found errors from comparison service
        logger.error(f"Contract validation error: {e}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "ContractNotFound",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Error comparing contracts: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ComparisonError",
                "message": "Failed to compare contracts",
                "details": str(e)
            }
        )


# Custom exception handler for better error responses
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unhandled errors.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "details": str(exc),
            "timestamp": format_timestamp()
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
