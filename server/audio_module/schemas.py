from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from ..shared.schemas import Claim, AudioSegment

class AudioAnalysisRequest(BaseModel):
    video_id: str
    title: str = ""  # [New] 제목 낚시 탐지를 위해 추가
    claims: List[Claim]

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