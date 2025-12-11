"""
Pydantic schemas for the Legal Contract Intelligence Platform.

These models define the API request/response structures and data validation
for contract analysis, risk assessment, and cost tracking.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, field_validator


class RiskLevel(str, Enum):
    """Risk severity levels for contract analysis."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskAnalysis(BaseModel):
    """Risk analysis results for a legal contract."""
    risk_level: RiskLevel = Field(..., description="Overall risk assessment level")
    risk_score: float = Field(..., ge=0, le=100, description="Numerical risk score (0-100)")
    identified_risks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of identified risks with details"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommended actions to mitigate risks"
    )
    compliance_issues: List[str] = Field(
        default_factory=list,
        description="Identified compliance or regulatory issues"
    )
    analysis_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the analysis was performed"
    )


class KeyTerms(BaseModel):
    """Extracted key terms and conditions from a contract."""
    parties: List[str] = Field(
        default_factory=list,
        description="Contract parties (companies/individuals)"
    )
    effective_date: Optional[str] = Field(
        None,
        description="Contract effective date"
    )
    expiration_date: Optional[str] = Field(
        None,
        description="Contract expiration date"
    )
    payment_terms: List[str] = Field(
        default_factory=list,
        description="Payment obligations and schedules"
    )
    termination_clauses: List[str] = Field(
        default_factory=list,
        description="Conditions under which contract can be terminated"
    )
    obligations: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Obligations for each party"
    )
    penalties: List[str] = Field(
        default_factory=list,
        description="Penalty clauses and consequences"
    )
    governing_law: Optional[str] = Field(
        None,
        description="Governing law jurisdiction"
    )
    additional_terms: Dict[str, Any] = Field(
        default_factory=dict,
        description="Other important terms identified"
    )


class ContractUploadResponse(BaseModel):
    """Response after uploading and parsing a contract."""
    contract_id: str = Field(..., description="Unique identifier for the contract")
    filename: str = Field(..., description="Original filename of the uploaded contract")
    parsed_text: str = Field(..., description="Extracted text content from the contract")
    sections: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Extracted legal sections with numbering"
    )
    tables: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted tables from the contract"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Contract metadata (type, dates, parties, etc.)"
    )
    key_terms: Optional[KeyTerms] = Field(
        None,
        description="Extracted key terms and conditions"
    )
    risk_analysis: Optional[RiskAnalysis] = Field(
        None,
        description="Initial risk analysis results"
    )
    processing_time_ms: float = Field(..., description="Time taken to process the contract")
    upload_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the contract was uploaded"
    )


class ContractQuery(BaseModel):
    """Query request for contract analysis."""
    contract_id: str = Field(..., description="Contract identifier to query")
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language question about the contract"
    )
    include_context: bool = Field(
        default=True,
        description="Whether to include relevant contract sections in response"
    )
    max_context_length: int = Field(
        default=2000,
        ge=500,
        le=8000,
        description="Maximum characters of context to include"
    )


class QueryResponse(BaseModel):
    """Response to a contract query."""
    query_id: str = Field(..., description="Unique identifier for this query")
    contract_id: str = Field(..., description="Contract that was queried")
    question: str = Field(..., description="Original question asked")
    answer: str = Field(..., description="Generated answer to the question")
    confidence_score: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence in the answer (0-1)"
    )
    relevant_sections: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Contract sections used to generate the answer"
    )
    citations: List[str] = Field(
        default_factory=list,
        description="Specific clauses or citations referenced"
    )
    model_used: str = Field(..., description="Gemini model used for generation")
    tokens_used: int = Field(..., description="Total tokens consumed")
    cost: float = Field(..., description="Cost of this query in USD")
    response_time_ms: float = Field(..., description="Time taken to generate response")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the query was processed"
    )


class ModelCostBreakdown(BaseModel):
    """Cost breakdown for a specific model."""
    model_name: str = Field(..., description="Gemini model name")
    total_calls: int = Field(default=0, description="Number of API calls")
    total_tokens: int = Field(default=0, description="Total tokens consumed")
    input_tokens: int = Field(default=0, description="Input tokens consumed")
    output_tokens: int = Field(default=0, description="Output tokens generated")
    total_cost: float = Field(default=0.0, description="Total cost in USD")


class CostAnalytics(BaseModel):
    """Aggregated cost analytics for API usage."""
    period: str = Field(..., description="Time period for analytics (e.g., 'daily', 'weekly')")
    start_date: datetime = Field(..., description="Start of analytics period")
    end_date: datetime = Field(..., description="End of analytics period")
    total_cost: float = Field(..., description="Total cost across all models in USD")
    total_tokens: int = Field(..., description="Total tokens consumed")
    total_calls: int = Field(..., description="Total API calls made")
    by_model: List[ModelCostBreakdown] = Field(
        default_factory=list,
        description="Cost breakdown by Gemini model"
    )
    by_operation: Dict[str, float] = Field(
        default_factory=dict,
        description="Cost breakdown by operation type"
    )
    daily_breakdown: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Daily cost breakdown within the period"
    )
    average_cost_per_query: float = Field(
        default=0.0,
        description="Average cost per query"
    )
    cost_trend: str = Field(
        default="stable",
        description="Cost trend analysis (increasing/decreasing/stable)"
    )

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        """Validate period is one of the allowed values."""
        allowed = ["daily", "weekly", "monthly", "custom"]
        if v not in allowed:
            raise ValueError(f"Period must be one of {allowed}")
        return v


class ContractMetadata(BaseModel):
    """Metadata extracted from a contract document."""
    contract_type: Optional[str] = Field(
        None,
        description="Type of contract (e.g., NDA, Employment, Lease)"
    )
    jurisdiction: Optional[str] = Field(
        None,
        description="Legal jurisdiction or governing law"
    )
    document_date: Optional[str] = Field(
        None,
        description="Date the document was created/signed"
    )
    parties: List[str] = Field(
        default_factory=list,
        description="Named parties in the contract"
    )
    page_count: int = Field(
        default=0,
        description="Number of pages in the document"
    )
    language: str = Field(
        default="en",
        description="Document language"
    )
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When metadata was extracted"
    )


class ParsedSection(BaseModel):
    """A parsed section from a legal document."""
    section_number: str = Field(..., description="Section identifier (e.g., '1.1', '2.3.4')")
    title: Optional[str] = Field(None, description="Section title")
    content: str = Field(..., description="Section content/text")
    level: int = Field(..., ge=1, description="Nesting level (1 = top level)")
    parent_section: Optional[str] = Field(
        None,
        description="Parent section number if nested"
    )


class ParsedTable(BaseModel):
    """A table extracted from a legal document."""
    table_number: int = Field(..., ge=1, description="Table sequence number in document")
    caption: Optional[str] = Field(None, description="Table caption or title")
    headers: List[str] = Field(default_factory=list, description="Column headers")
    rows: List[List[str]] = Field(default_factory=list, description="Table data rows")
    markdown: str = Field(..., description="Markdown representation of the table")
    location: str = Field(..., description="Location in document (page/section)")


# API-specific request/response models for FastAPI endpoints

class ContractQueryRequest(BaseModel):
    """Request body for querying a contract."""
    query: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language question about the contract"
    )
    include_context: bool = Field(
        default=True,
        description="Whether to include relevant sections in response"
    )


class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the error occurred"
    )


class ContractAnalysisResponse(BaseModel):
    """Response after uploading and analyzing a contract."""
    contract_id: str = Field(..., description="Unique identifier for the contract")
    filename: str = Field(..., description="Original filename")
    risk_analysis: Optional[Dict[str, Any]] = Field(
        None,
        description="Risk analysis results"
    )
    key_terms: Optional[Dict[str, Any]] = Field(
        None,
        description="Extracted key terms"
    )
    total_cost: float = Field(..., description="Total API cost in USD")
    errors: List[str] = Field(
        default_factory=list,
        description="Any errors encountered during processing"
    )
    processing_time_ms: Optional[float] = Field(
        None,
        description="Time taken to process"
    )


class ContractQueryResponse(BaseModel):
    """Response to a contract query."""
    contract_id: str = Field(..., description="Contract that was queried")
    query: str = Field(..., description="Original question")
    answer: str = Field(..., description="Generated answer")
    cost: float = Field(..., description="Cost of this query in USD")
    relevant_sections: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Contract sections used for the answer"
    )


class ContractDetailsResponse(BaseModel):
    """Full contract details from FalkorDB graph."""
    contract_id: str = Field(..., description="Contract identifier")
    filename: str = Field(..., description="Original filename")
    upload_date: datetime = Field(..., description="When contract was uploaded")
    risk_score: Optional[float] = Field(None, description="Risk score (0-10)")
    risk_level: Optional[str] = Field(None, description="Risk level (low/medium/high)")
    companies: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Company/party information"
    )
    clauses: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Contract clauses"
    )
    risk_factors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Identified risk factors"
    )


class GlobalSearchResponse(BaseModel):
    """Response for global contract search across all contracts."""
    query: str = Field(..., description="The search query used")
    results: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of matching contracts with their details"
    )
    total: int = Field(..., description="Total number of matching contracts")


class ContractSummary(BaseModel):
    """Summary for list view."""
    contract_id: str = Field(..., description="Contract identifier")
    filename: str = Field(..., description="Original filename")
    upload_date: datetime = Field(..., description="When contract was uploaded")
    risk_score: Optional[float] = Field(None, description="Risk score (0-10)")
    risk_level: Optional[str] = Field(None, description="Risk level (low/medium/high)")
    party_count: int = Field(default=0, description="Number of parties in the contract")


class ContractListResponse(BaseModel):
    """Paginated contract list."""
    contracts: List[ContractSummary] = Field(
        default_factory=list,
        description="List of contract summaries"
    )
    total: int = Field(..., description="Total number of contracts matching filters")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    has_more: bool = Field(..., description="Whether there are more pages available")


class BatchUploadResult(BaseModel):
    """Result for a single file in a batch upload."""
    filename: str = Field(..., description="Original filename")
    contract_id: Optional[str] = Field(None, description="Contract ID if successful")
    status: str = Field(..., description="Status: 'success' or 'failed'")
    error: Optional[str] = Field(None, description="Error message if failed")
    risk_level: Optional[str] = Field(None, description="Risk level if successful")


class BatchUploadResponse(BaseModel):
    """Response after batch uploading multiple contracts."""
    total: int = Field(..., description="Total number of files uploaded")
    successful: int = Field(..., description="Number of successfully processed files")
    failed: int = Field(..., description="Number of failed files")
    results: List[BatchUploadResult] = Field(
        default_factory=list,
        description="Individual results for each file"
    )
    total_cost: float = Field(..., description="Total cost across all files in USD")
    processing_time_ms: float = Field(..., description="Total processing time in milliseconds")


class ContractComparisonRequest(BaseModel):
    """Request to compare two contracts."""
    contract_id_a: str = Field(..., description="First contract ID to compare")
    contract_id_b: str = Field(..., description="Second contract ID to compare")
    aspects: List[str] = Field(
        default=["payment_terms", "liability", "termination", "indemnification"],
        description="Aspects to compare between contracts"
    )

    @field_validator("aspects")
    @classmethod
    def validate_aspects(cls, v: List[str]) -> List[str]:
        """Validate that aspects list is not empty and has reasonable length."""
        if not v:
            raise ValueError("At least one aspect must be specified")
        if len(v) > 10:
            raise ValueError("Maximum 10 aspects allowed per comparison")
        return v


class ContractComparisonResponse(BaseModel):
    """Response from contract comparison."""
    contract_a: Dict[str, str] = Field(
        ...,
        description="First contract metadata (id, filename)"
    )
    contract_b: Dict[str, str] = Field(
        ...,
        description="Second contract metadata (id, filename)"
    )
    comparisons: List[Dict[str, Any]] = Field(
        ...,
        description="Comparison results for each aspect"
    )
    total_cost: float = Field(
        ...,
        description="Total API cost for comparison in USD"
    )


# Graph RAG schemas

class GraphRAGQueryRequest(BaseModel):
    """Request for Graph RAG query."""
    query: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Question to answer using hybrid retrieval"
    )
    contract_id: Optional[str] = Field(
        None,
        description="Specific contract (None = search all contracts)"
    )
    n_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of context items to retrieve"
    )


class GraphRAGSource(BaseModel):
    """Source attribution for Graph RAG response."""
    index: int = Field(..., description="Source number for citation")
    type: str = Field(..., description="Source type: 'semantic' or 'graph'")
    contract_id: str = Field(..., description="Contract this source came from")
    score: float = Field(..., description="RRF relevance score")
    preview: str = Field(..., description="Content preview (first 100 chars)")


class GraphRAGQueryResponse(BaseModel):
    """Response from Graph RAG query."""
    answer: str = Field(..., description="Generated answer to the question")
    sources: List[GraphRAGSource] = Field(
        default_factory=list,
        description="Source attribution with citations"
    )
    semantic_results: int = Field(..., description="Number of semantic search results")
    graph_results: int = Field(..., description="Number of graph context results")
    cost: float = Field(..., description="Cost of this query in USD")
