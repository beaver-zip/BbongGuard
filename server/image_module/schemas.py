from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from ..shared.schemas import Claim

class ImageAnalysisRequest(BaseModel):
    video_id: str
    claims: List[Claim] = []
    title: str = ""

class ClaimVerdict(BaseModel):
    claim_id: str
    image_support_score: float
    image_contradiction_score: float
    notes: List[str]
    frames: List[Dict[str, Any]]

class ImageModuleResult(BaseModel):
    modality: str = "image"
    video_id: str
    analysis_summary: str
    claims: List[ClaimVerdict]
    frames: List[Dict[str, Any]] = []
    processing_time_ms: float
    status: str
    overall_contradiction_score: float = 0.0
    error_message: Optional[str] = None
