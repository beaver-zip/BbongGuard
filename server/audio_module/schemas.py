from pydantic import BaseModel
from typing import List, Optional
from ..shared.schemas import Claim, AudioSegment

class AudioAnalysisRequest(BaseModel):
    video_id: str
    title: str = "" 
    description: str = ""
    claims: List[Claim] = []
    transcript: Optional[str] = None

class ClaimVerdict(BaseModel):
    claim_id: str
    audio_support_score: float
    notes: List[str]
    segments: List[AudioSegment]

class AudioModuleResult(BaseModel):
    modality: str = "audio"
    video_id: str
    analysis_summary: str
    claims: List[ClaimVerdict]
    processing_time_ms: float
    status: str
    error_message: Optional[str] = None
    transcript: Optional[str] = None