"""멀티모달 분석을 위한 공통 데이터 스키마"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

# 중요도 타입
Importance = Literal["Low", "Medium", "High"]

class Claim(BaseModel):
    """검증이 필요한 주장 (모든 모듈에서 공유)"""
    claim_id: str = Field(..., description="주장 고유 ID")
    claim_text: str = Field(..., description="주장 텍스트")
    category: str = Field(default="일반", description="주장 카테고리")
    importance: str = Field(default="Medium", description="주장 중요도 (High/Medium/Low)")
    source: Optional[Dict[str, Any]] = Field(default=None, description="주장 추출 위치 정보 (timestamp 등)")

class VideoMeta(BaseModel):
    """영상 메타데이터 및 자막"""
    video_id: str
    url: str
    duration_sec: int = 0
    language: str = "ko"
    has_official_captions: bool = False
    transcript: Optional[List[Dict[str, Any]]] = Field(default=None, description="자막 리스트 [{'text':..., 'start':..., 'end':...}]")

class FrameFeature(BaseModel):
    """이미지 프레임 특징"""
    frame_id: str
    timestamp: float
    ocr_text: str = ""
    caption: str = ""
    relevance_score: float = 0.0  # Claim과의 관련성

class AudioSegment(BaseModel):
    """오디오 구간 특징"""
    segment_id: str
    start: float
    end: float
    transcript_text: str
    tone: str = ""
    emotion: str = ""
    spoof_score: float = 0.0
    relevance_score: float = 0.0

class ErrorResponse(BaseModel):
    """에러 응답"""
    success: bool = Field(False, description="항상 False")
    error: str = Field(..., description="에러 메시지")
    detail: Optional[str] = Field(None, description="상세 에러 정보")

class HealthResponse(BaseModel):
    """서버 상태 응답"""
    status: str = Field(..., description="서버 상태 ('healthy' 또는 'unhealthy')")
    version: str = Field(..., description="API 버전")

