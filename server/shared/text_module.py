"""텍스트 모듈 입출력 정의"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# ===== 텍스트 모듈 전용 모델 =====

class Claim(BaseModel):
    """
    검증이 필요한 주장 모델.
    """
    claim_id: str = Field(..., description="주장 ID")
    claim_text: str = Field(..., description="주장 내용")
    category: str = Field(..., description="주장 카테고리")
    importance: str = Field(..., description="중요도 (High/Medium/Low)")


class Evidence(BaseModel):
    """
    주장 검증을 위한 근거 자료 모델.
    """
    source_title: str = Field(..., description="출처 제목")
    source_url: str = Field(..., description="출처 URL")
    domain: str = Field(..., description="출처 도메인")
    snippet: str = Field(..., description="관련 내용 발췌")
    published_date: Optional[str] = Field(None, description="발행일")


class ClaimVerdict(BaseModel):
    """
    단일 주장에 대한 판정 결과 모델.
    """
    claim_id: str = Field(..., description="주장 ID")
    claim_text: str = Field(..., description="주장 내용")
    category: str = Field(..., description="주장 카테고리")
    verdict_status: str = Field("insufficient_evidence", description="판정 상태 (verified_true/verified_false/insufficient_evidence)")
    is_fake: bool = Field(..., description="가짜뉴스 여부 (True: 가짜, False: 진실/확인불가)")
    verdict_reason: str = Field(..., description="판정 이유")
    evidence: List[Evidence] = Field(default_factory=list, description="근거 자료 목록")
    processing_time_ms: float = Field(0, description="처리 시간 (ms)")


# ===== 텍스트 모듈 출력 =====

class Finding(BaseModel):
    """
    텍스트 모듈 분석 중 발견된 특이사항 모델.
    """
    finding_id: str = Field(..., description="발견사항 ID")
    finding_type: str = Field(..., description="발견사항 유형 (예: claim)")
    description: str = Field(..., description="설명")
    is_problematic: bool = Field(..., description="문제성 여부")
    severity: str = Field(..., description="심각도 (High/Medium/Low)")
    evidence_summary: str = Field(..., description="근거 요약")
    details: dict = Field(default_factory=dict, description="추가 상세 정보")


class TextModuleResult(BaseModel):
    """
    텍스트 모듈의 전체 분석 결과 모델.
    """

    modality: str = Field("text", description="모듈 유형")
    video_id: str = Field(..., description="영상 ID")

    # 분석 요약
    analysis_summary: str = Field(..., description="전체 분석 요약")

    # 발견 사항
    findings: List[Finding] = Field(default_factory=list, description="발견된 특이사항 목록")
    total_findings: int = Field(0, description="총 발견사항 수")
    problematic_findings_count: int = Field(0, description="문제성 발견사항 수")

    # 모듈 평가
    module_assessment: str = Field(..., description="모듈 종합 평가")
    key_concerns: List[str] = Field(default_factory=list, description="주요 우려사항 목록")

    # 메타데이터
    processing_time_ms: float = Field(0, description="처리 시간 (ms)")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="분석 시각")
    status: str = Field("success", description="처리 상태")
    error_message: Optional[str] = Field(None, description="에러 메시지")

    # 텍스트 모듈 특화 데이터
    claims: List[ClaimVerdict] = Field(default_factory=list, description="주장별 판정 결과")
    transcript: Optional[str] = Field(None, description="STT 결과 (재활용용)")


# ===== API 요청 =====

class TextAnalysisRequest(BaseModel):
    """
    텍스트 모듈 분석 요청 모델.
    """
    video_id: str = Field(..., description="영상 ID")
    title: str = Field(..., description="영상 제목")
    description: str = Field("", description="영상 설명")
    published_at: Optional[str] = Field(None, description="영상 게시일")
    transcript: Optional[str] = Field(None, description="자막 텍스트")
    max_claims: Optional[int] = Field(None, description="최대 추출 주장 수")
    enable_caching: bool = Field(True, description="캐싱 사용 여부")
    duration_sec: int = Field(0, description="영상 길이 (초)")
