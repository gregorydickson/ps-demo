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
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Import services
try:
    # Try relative imports first (when run as module)
    from .services.cost_tracker import CostTracker
    from .services.graph_store import ContractGraphStore
    from .services.vector_store import ContractVectorStore
    from .workflows.contract_analysis_workflow import get_workflow
    from .workflows.qa_workflow import QAWorkflow
    from .workflows.graph_rag_workflow import GraphRAGWorkflow
    from .utils.request_context import set_request_id, clear_request_context
    from .models.schemas import (
        ContractAnalysisResponse,
        ContractQueryRequest,
        ContractQueryResponse,
        ContractDetailsResponse,
        CostAnalytics,
        ErrorResponse,
        GraphRAGQueryRequest,
        GraphRAGQueryResponse
    )
except ImportError:
    # Fall back to absolute imports (when run directly)
    from backend.services.cost_tracker import CostTracker
    from backend.services.graph_store import ContractGraphStore
    from backend.services.vector_store import ContractVectorStore
    from backend.workflows.contract_analysis_workflow import get_workflow
    from backend.workflows.qa_workflow import QAWorkflow
    from backend.workflows.graph_rag_workflow import GraphRAGWorkflow
    from backend.utils.request_context import set_request_id, clear_request_context
    from backend.models.schemas import (
        ContractAnalysisResponse,
        ContractQueryRequest,
        ContractQueryResponse,
        ContractDetailsResponse,
        CostAnalytics,
        ErrorResponse,
        GraphRAGQueryRequest,
        GraphRAGQueryResponse
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

# Global service instances
cost_tracker: Optional[CostTracker] = None
graph_store: Optional[ContractGraphStore] = None
vector_store: Optional[ContractVectorStore] = None
workflow = None
qa_workflow: Optional[QAWorkflow] = None
graph_rag_workflow: Optional[GraphRAGWorkflow] = None


@app.on_event("startup")
async def startup_event():
    """
    Initialize services on application startup.
    """
    global cost_tracker, graph_store, vector_store, workflow, qa_workflow, graph_rag_workflow

    logger.info("Starting Contract Intelligence API...")

    try:
        # Initialize CostTracker
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        cost_tracker = CostTracker(redis_url=redis_url)
        logger.info(f"CostTracker initialized with Redis at {redis_url}")

        # Initialize ContractGraphStore
        graph_store = ContractGraphStore()
        logger.info("ContractGraphStore initialized with FalkorDB")

        # Initialize ContractVectorStore
        vector_store = ContractVectorStore()
        logger.info("ContractVectorStore initialized with ChromaDB")

        # Initialize workflow
        workflow = get_workflow(initialize_stores=True)
        logger.info("Contract analysis workflow initialized")

        # Initialize QA workflow
        qa_workflow = QAWorkflow(cost_tracker=cost_tracker)
        logger.info("QA workflow initialized")

        # Initialize Graph RAG workflow
        graph_rag_workflow = GraphRAGWorkflow(
            vector_store=vector_store,
            graph_store=graph_store,
            cost_tracker=cost_tracker
        )
        logger.info("Graph RAG workflow initialized")

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

    if graph_store:
        graph_store.close()
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
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Detailed health check including service status.
    """
    redis_healthy = cost_tracker.health_check() if cost_tracker else False

    return {
        "status": "healthy" if redis_healthy else "degraded",
        "services": {
            "redis": "up" if redis_healthy else "down",
            "falkordb": "up" if graph_store else "down",
            "workflow": "up" if workflow else "down"
        },
        "timestamp": datetime.utcnow().isoformat()
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
    4. Stores in ChromaDB and FalkorDB
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
    "/api/contracts/{contract_id}",
    response_model=ContractDetailsResponse,
    tags=["Contracts"]
)
async def get_contract_details(
    contract_id: str = Path(..., description="Contract identifier")
):
    """
    Retrieve full contract details from FalkorDB graph store.

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
        # Retrieve from FalkorDB
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
    "/api/contracts/graph-query",
    response_model=GraphRAGQueryResponse,
    tags=["Contracts"]
)
async def graph_rag_query(
    request: GraphRAGQueryRequest
):
    """
    Query contracts using Graph RAG (hybrid semantic + graph retrieval).

    This endpoint provides enhanced Q&A by combining:
    - Semantic search over document text (ChromaDB)
    - Graph traversal for related entities (FalkorDB)
    - Re-ranked results using Reciprocal Rank Fusion (RRF)

    The hybrid approach provides richer context by including:
    - Relevant document chunks (semantic similarity)
    - Company/party information (graph relationships)
    - Related clauses and risk factors (graph context)

    Args:
        request: GraphRAGQueryRequest with query, optional contract_id, and n_results

    Returns:
        GraphRAGQueryResponse with answer, sources, and cost

    Raises:
        400: Invalid request (query too short, invalid n_results)
        503: Graph RAG workflow not initialized
        500: Query processing error
    """
    logger.info(
        f"Graph RAG query: {request.query[:50]}... "
        f"(contract_id={request.contract_id}, n_results={request.n_results})"
    )

    if not graph_rag_workflow:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ServiceUnavailable",
                "message": "Graph RAG workflow not initialized"
            }
        )

    try:
        # Run Graph RAG workflow
        result = await graph_rag_workflow.run(
            query=request.query,
            contract_id=request.contract_id,
            n_results=request.n_results,
            include_sources=True
        )

        # Check for errors
        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GraphRAGError",
                    "message": result["error"]
                }
            )

        # Build response
        response = GraphRAGQueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            semantic_results=result["retrieval_response"].semantic_count,
            graph_results=result["retrieval_response"].graph_count,
            cost=result["cost"]
        )

        logger.info(
            f"Graph RAG query completed: {response.semantic_results} semantic + "
            f"{response.graph_results} graph results, cost ${response.cost:.6f}"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Graph RAG query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GraphRAGError",
                "message": "Failed to process Graph RAG query",
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
            "timestamp": datetime.utcnow().isoformat()
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
