"""멀티모달 최종 통합 결과"""

from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime


# ===== 각 모듈 결과의 공통 인터페이스 =====

class ModuleResult(BaseModel):
    """
    모든 모듈 결과의 공통 필드 모델.
    """
    modality: str = Field(..., description="모듈 유형 (text/image/audio)")
    video_id: str = Field(..., description="영상 ID")
    analysis_summary: str = Field(..., description="분석 요약")
    module_assessment: str = Field(..., description="모듈 평가 (suspicious/normal/inconclusive)")
    key_concerns: List[str] = Field(default_factory=list, description="주요 우려사항")
    processing_time_ms: float = Field(0, description="처리 시간 (ms)")
    status: str = Field("success", description="처리 상태")


# ===== LLM 최종 통합 판단 =====

class FinalVerdict(BaseModel):
    """
    LLM이 모든 모듈 결과를 종합한 최종 판단 모델.
    """

    # 최종 판단
    is_fake_news: bool = Field(..., description="가짜뉴스 여부")
    confidence_level: str = Field(..., description="신뢰도 (high/medium/low)")

    # 종합 근거
    overall_reasoning: str = Field(..., description="종합 판단 근거")

    # 모듈별 요약
    text_analysis_summary: Optional[str] = Field(None, description="텍스트 분석 요약")
    image_analysis_summary: Optional[str] = Field(None, description="이미지 분석 요약")
    audio_analysis_summary: Optional[str] = Field(None, description="오디오 분석 요약")

    # 상세 분석 내용
    image_analysis_details: Optional[str] = Field(None, description="이미지 모듈 상세 분석 내용")
    audio_analysis_details: Optional[str] = Field(None, description="오디오 모듈 상세 분석 내용")

    # 핵심 판단 근거
    key_evidence: List[str] = Field(default_factory=list, description="핵심 증거 목록")
    
    # 텍스트 모듈 출처 (판단 근거와 URL 쌍)
    text_sources: List[dict] = Field(default_factory=list, description="텍스트 모듈 출처 (reason, url)")

    # 사용자 권장 사항
    recommendation: str = Field(..., description="사용자 권장 사항")


# ===== 멀티모달 통합 결과 =====

class MultiModalAnalysisResult(BaseModel):
    """
    전체 멀티모달 분석 최종 결과 모델.
    """

    video_id: str = Field(..., description="영상 ID")

    # 각 모듈 결과 (Any는 text_module.TextModuleResult 등으로 대체)
    text_result: Optional[Any] = Field(None, description="텍스트 분석 결과")
    image_result: Optional[Any] = Field(None, description="이미지 분석 결과")
    audio_result: Optional[Any] = Field(None, description="오디오 분석 결과")

    # LLM 최종 판단
    final_verdict: FinalVerdict = Field(..., description="최종 종합 판단")

    # 전체 메타데이터
    total_processing_time_ms: float = Field(0, description="총 처리 시간 (ms)")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="분석 시각")
