"""텍스트 모듈 입출력 정의"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# ===== 텍스트 모듈 전용 모델 =====

class Claim(BaseModel):
    """검증이 필요한 주장"""
    claim_id: str
    claim_text: str
    category: str
    importance: str  # high/medium/low


class Evidence(BaseModel):
    """검증 근거 자료"""
    source_title: str
    source_url: str
    domain: str
    snippet: str
    published_date: Optional[str] = None


class ClaimVerdict(BaseModel):
    """단일 주장 판정 결과"""
    claim_id: str
    claim_text: str
    category: str
    verdict_status: str = "insufficient_evidence"  # "verified_true" | "verified_false" | "insufficient_evidence"
    is_fake: bool  # 하위 호환성 유지
    verdict_reason: str
    evidence: List[Evidence] = Field(default_factory=list)
    processing_time_ms: float = 0


# ===== 텍스트 모듈 출력 =====

class Finding(BaseModel):
    """텍스트 모듈의 발견 사항 (주장)"""
    finding_id: str
    finding_type: str  # "claim"
    description: str
    is_problematic: bool
    severity: str  # high/medium/low
    evidence_summary: str
    details: dict = Field(default_factory=dict)


class TextModuleResult(BaseModel):
    """텍스트 모듈 분석 결과"""

    modality: str = "text"
    video_id: str

    # 분석 요약
    analysis_summary: str

    # 발견 사항
    findings: List[Finding] = Field(default_factory=list)
    total_findings: int = 0
    problematic_findings_count: int = 0

    # 모듈 평가
    module_assessment: str  # suspicious/normal/inconclusive
    key_concerns: List[str] = Field(default_factory=list)

    # 메타데이터
    processing_time_ms: float = 0
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "success"
    error_message: Optional[str] = None

    # 텍스트 모듈 특화 데이터
    claims: List[ClaimVerdict] = Field(default_factory=list)


# ===== API 요청 =====

class TextAnalysisRequest(BaseModel):
    """텍스트 모듈 분석 요청"""
    video_id: str
    title: str
    description: str = ""
    comments: List[str] = Field(default_factory=list)
    transcript: Optional[str] = None
    max_claims: Optional[int] = None
    enable_caching: bool = True
    duration_sec: int = 0  # 영상 길이 (초)
