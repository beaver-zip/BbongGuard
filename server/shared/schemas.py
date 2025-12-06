"""멀티모달 분석을 위한 공통 데이터 스키마"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

# 중요도 타입
Importance = Literal["Low", "Medium", "High"]

class Claim(BaseModel):
    """
    검증이 필요한 주장 데이터 모델.
    모든 분석 모듈(Text, Image, Audio)에서 공통으로 사용됩니다.
    """
    claim_id: str = Field(..., description="주장 고유 ID (UUID 등)")
    claim_text: str = Field(..., description="검증할 주장의 텍스트 내용")
    category: str = Field(default="일반", description="주장 카테고리 (예: 정치, 경제, 건강)")
    importance: str = Field(default="Medium", description="주장 중요도 (High/Medium/Low)")
    source: Optional[Dict[str, Any]] = Field(default=None, description="주장 추출 위치 정보 (timestamp 등)")

class VideoMeta(BaseModel):
    """
    유튜브 영상의 메타데이터 및 자막 정보.
    """
    video_id: str = Field(..., description="유튜브 영상 ID")
    url: str = Field(..., description="영상 URL")
    duration_sec: int = Field(0, description="영상 길이 (초)")
    language: str = Field("ko", description="영상 언어 코드")
    has_official_captions: bool = Field(False, description="공식 자막 존재 여부")
    transcript: Optional[List[Dict[str, Any]]] = Field(default=None, description="자막 리스트 [{'text':..., 'start':..., 'end':...}]")

class FrameFeature(BaseModel):
    """
    이미지 프레임 분석 결과.
    """
    frame_id: str = Field(..., description="프레임 식별자")
    timestamp: float = Field(..., description="프레임 시간 (초)")
    ocr_text: str = Field("", description="프레임 내 OCR 추출 텍스트")
    caption: str = Field("", description="프레임 설명 (Captioning)")
    relevance_score: float = Field(0.0, description="Claim과의 관련성 점수 (0.0~1.0)")

class AudioSegment(BaseModel):
    """
    오디오 구간 분석 결과.
    """
    segment_id: str = Field(..., description="구간 식별자")
    start: float = Field(..., description="시작 시간 (초)")
    end: float = Field(..., description="종료 시간 (초)")
    transcript_text: str = Field(..., description="해당 구간의 STT 텍스트")
    tone: str = Field("", description="어조/톤 분석 결과")
    emotion: str = Field("", description="감정 분석 결과")
    spoof_score: float = Field(0.0, description="음성 조작/합성 의심 점수")
    relevance_score: float = Field(0.0, description="Claim과의 관련성 점수")

class ErrorResponse(BaseModel):
    """
    API 에러 응답 모델.
    """
    success: bool = Field(False, description="성공 여부 (항상 False)")
    error: str = Field(..., description="에러 메시지 요약")
    detail: Optional[str] = Field(None, description="상세 에러 내용 (디버깅용)")

class HealthResponse(BaseModel):
    """
    서버 상태 확인 응답 모델.
    """
    status: str = Field(..., description="서버 상태 ('healthy' 또는 'unhealthy')")
    version: str = Field(..., description="API 버전")

