"""
Graph schemas for Neo4j contract storage.

Defines node and relationship schemas for representing legal contracts
in a graph database structure.
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class CompanyNode(BaseModel):
    """Company/Party node in the contract graph."""

    name: str = Field(..., description="Company name")
    role: str = Field(..., description="Role in contract (e.g., 'vendor', 'client')")
    company_id: Optional[str] = Field(None, description="Unique company identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Acme Corp",
                "role": "vendor",
                "company_id": "acme_corp_123"
            }
        }


class ClauseNode(BaseModel):
    """Clause/Section node in the contract graph."""

    section_name: str = Field(..., description="Name of the clause section")
    content: str = Field(..., description="Full text content of the clause")
    clause_type: Optional[str] = Field(None, description="Type of clause (e.g., 'payment', 'termination')")
    importance: Optional[str] = Field("medium", description="Importance level: low, medium, high")

    class Config:
        json_schema_extra = {
            "example": {
                "section_name": "Payment Terms",
                "content": "Payment shall be made within 30 days...",
                "clause_type": "payment",
                "importance": "high"
            }
        }


class RiskFactorNode(BaseModel):
    """Risk factor node in the contract graph."""

    concern: str = Field(..., description="Description of the risk concern")
    risk_level: str = Field(..., description="Risk level: low, medium, high")
    section: Optional[str] = Field(None, description="Related section name")
    recommendation: Optional[str] = Field(None, description="Recommended action")

    class Config:
        json_schema_extra = {
            "example": {
                "concern": "Unlimited liability exposure",
                "risk_level": "high",
                "section": "Liability Clause",
                "recommendation": "Negotiate a liability cap"
            }
        }


class ContractNode(BaseModel):
    """Contract node - central entity in the graph."""

    contract_id: str = Field(..., description="Unique contract identifier")
    filename: str = Field(..., description="Original filename")
    upload_date: datetime = Field(default_factory=datetime.now, description="Upload timestamp")
    risk_score: Optional[float] = Field(None, ge=0, le=10, description="Overall risk score (0-10)")
    risk_level: Optional[str] = Field(None, description="Overall risk level: low, medium, high")
    payment_amount: Optional[str] = Field(None, description="Payment amount from contract")
    payment_frequency: Optional[str] = Field(None, description="Payment frequency")
    has_termination_clause: Optional[bool] = Field(None, description="Whether contract has termination clause")
    liability_cap: Optional[str] = Field(None, description="Liability cap amount or 'unlimited'")

    class Config:
        json_schema_extra = {
            "example": {
                "contract_id": "contract_123",
                "filename": "service_agreement.pdf",
                "upload_date": "2024-01-15T10:30:00",
                "risk_score": 6.5,
                "risk_level": "medium",
                "payment_amount": "$50,000",
                "payment_frequency": "monthly",
                "has_termination_clause": True,
                "liability_cap": "$100,000"
            }
        }


class ContractRelationship(BaseModel):
    """Represents a relationship in the contract graph."""

    type: str = Field(..., description="Relationship type (PARTY_TO, CONTAINS, HAS_RISK)")
    source: str = Field(..., description="Source node type")
    target: str = Field(..., description="Target node type")
    properties: Optional[dict] = Field(default_factory=dict, description="Additional properties")


class ContractGraph(BaseModel):
    """Complete contract graph structure with all nodes and relationships."""

    contract: ContractNode
    companies: List[CompanyNode] = Field(default_factory=list)
    clauses: List[ClauseNode] = Field(default_factory=list)
    risk_factors: List[RiskFactorNode] = Field(default_factory=list)
    relationships: List[ContractRelationship] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "contract": {
                    "contract_id": "contract_123",
                    "filename": "agreement.pdf",
                    "risk_score": 5.0,
                    "risk_level": "medium"
                },
                "companies": [
                    {"name": "Acme Corp", "role": "vendor"},
                    {"name": "Client Inc", "role": "client"}
                ],
                "clauses": [
                    {
                        "section_name": "Payment Terms",
                        "content": "Payment within 30 days",
                        "clause_type": "payment"
                    }
                ],
                "risk_factors": [
                    {
                        "concern": "Late payment penalties unclear",
                        "risk_level": "medium",
                        "section": "Payment Terms"
                    }
                ],
                "relationships": []
            }
        }
