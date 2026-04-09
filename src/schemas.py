from typing import List, Optional, Literal
from pydantic import BaseModel, Field

RelationshipLabel = Literal["Acquisition", "Merger", "Subsidiary", "None/Unclear"]

class DiscoveryItem(BaseModel):
    related_company: str
    relationship_type: RelationshipLabel
    confidence: float = Field(ge=0.0, le=1.0)
    event_year: Optional[str] = None
    source_authority: Literal["high", "medium", "low"]
    recency: Literal["high", "medium", "low"]
    clarity: Literal["high", "medium", "low"]
    evidence_summary: str
    evidence_urls: List[str]

class DiscoveryResponse(BaseModel):
    seed_company: str
    discoveries: List[DiscoveryItem]

class VerificationResponse(BaseModel):
    seed_company: str
    related_company: str
    relationship_type: RelationshipLabel
    confidence: float = Field(ge=0.0, le=1.0)
    source_authority: Literal["high", "medium", "low"]
    recency: Literal["high", "medium", "low"]
    clarity: Literal["high", "medium", "low"]
    evidence_summary: str
    evidence_urls: List[str]
    needs_review: bool

class ConsensusResult(BaseModel):
    seed_company: str
    related_company: str
    final_label: RelationshipLabel
    final_confidence: float
    agreement_count: int
    num_models: int
    needs_resolution: bool
    evidence_urls: List[str]