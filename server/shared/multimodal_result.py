"""멀티모달 최종 통합 결과"""

from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime


# ===== 각 모듈 결과의 공통 인터페이스 =====

class ModuleResult(BaseModel):
    """모든 모듈 결과의 공통 필드"""
    modality: str  # text/image/audio
    video_id: str
    analysis_summary: str
    module_assessment: str  # suspicious/normal/inconclusive
    key_concerns: List[str] = Field(default_factory=list)
    processing_time_ms: float = 0
    status: str = "success"


# ===== LLM 최종 통합 판단 =====

class FinalVerdict(BaseModel):
    """LLM이 모든 모듈 결과를 종합한 최종 판단"""

    # 최종 판단
    is_fake_news: bool
    confidence_level: str  # high/medium/low

    # 종합 근거
    overall_reasoning: str  # "이 영상은 가짜뉴스일 가능성이 높습니다. 근거는..."

    # 모듈별 요약
    text_analysis_summary: Optional[str] = None
    image_analysis_summary: Optional[str] = None
    audio_analysis_summary: Optional[str] = None

    # 핵심 판단 근거
    key_evidence: List[str] = Field(default_factory=list)
    
    # 텍스트 모듈 출처 (판단 근거와 URL 쌍)
    text_sources: List[dict] = Field(default_factory=list)  # [{"reason": "...", "url": "..."}]

    # 사용자 권장 사항
    recommendation: str


# ===== 멀티모달 통합 결과 =====

class MultiModalAnalysisResult(BaseModel):
    """전체 멀티모달 분석 최종 결과"""

    video_id: str

    # 각 모듈 결과 (Any는 text_module.TextModuleResult 등으로 대체)
    text_result: Optional[Any] = None
    image_result: Optional[Any] = None
    audio_result: Optional[Any] = None

    # LLM 최종 판단
    final_verdict: FinalVerdict

    # 전체 메타데이터
    total_processing_time_ms: float = 0
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
