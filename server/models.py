"""
Pydantic 모델 정의 (API 요청/응답 스키마)
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# ===== 요청 모델 =====

class RelatedVideoInfo(BaseModel):
    """관련 영상 정보"""
    videoId: Optional[str] = None
    title: str = ""
    description: Optional[str] = ""
    channelTitle: Optional[str] = None
    thumbnailUrl: Optional[str] = None


class AnalyzeRequest(BaseModel):
    """영상 분석 요청 (Chrome Extension에서 전송)"""
    videoId: str = Field(..., description="YouTube 영상 ID")
    title: str = Field(..., description="영상 제목")
    description: str = Field(default="", description="영상 설명")
    channelTitle: Optional[str] = Field(None, description="채널 이름")
    views: Optional[int] = Field(None, description="조회수")
    likes: Optional[int] = Field(None, description="좋아요 수")
    thumbnailUrl: Optional[str] = Field(None, description="썸네일 URL")
    comments: List[str] = Field(default_factory=list, description="댓글 목록")
    tags: Optional[List[str]] = Field(default_factory=list, description="태그 목록")
    relatedVideos: List[RelatedVideoInfo] = Field(
        default_factory=list,
        description="관련 영상 목록 (최대 9개)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "videoId": "dQw4w9WgXcQ",
                "title": "Example Video Title",
                "description": "This is an example video description",
                "channelTitle": "Example Channel",
                "views": 1000000,
                "likes": 50000,
                "comments": [
                    "Great video!",
                    "Very informative",
                    "Thanks for sharing"
                ],
                "tags": ["example", "tutorial"],
                "relatedVideos": [
                    {
                        "videoId": "abc123",
                        "title": "Related Video 1",
                        "description": "Description of related video"
                    }
                ]
            }
        }


# ===== 응답 모델 =====

class PredictionDetails(BaseModel):
    """예측 상세 정보"""
    fake_probability: float = Field(..., description="가짜뉴스일 확률 (0~1)")
    real_probability: float = Field(..., description="진짜뉴스일 확률 (0~1)")
    model_type: str = Field(default="OR-TDC", description="사용된 모델 타입")
    text_combination: str = Field(default="TDC", description="사용된 텍스트 조합")


class AnalyzeResponse(BaseModel):
    """영상 분석 응답"""
    success: bool = Field(..., description="분석 성공 여부")
    videoId: str = Field(..., description="분석한 영상 ID")
    prediction: str = Field(..., description="예측 결과 ('Fake' 또는 'Real')")
    fakeProbability: float = Field(..., description="가짜뉴스일 확률 (0~1)")
    confidence: float = Field(..., description="예측 신뢰도 (0~1)")
    evidence: Optional[str] = Field(None, description="판정 근거 (선택)")
    details: PredictionDetails = Field(..., description="상세 예측 정보")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "videoId": "dQw4w9WgXcQ",
                "prediction": "Real",
                "fakeProbability": 0.5,
                "confidence": 0.5,
                "evidence": None,
                "details": {
                    "fake_probability": 0.5,
                    "real_probability": 0.5,
                    "model_type": "OR-TDC",
                    "text_combination": "TDC"
                }
            }
        }


class ErrorResponse(BaseModel):
    """에러 응답"""
    success: bool = Field(False, description="항상 False")
    error: str = Field(..., description="에러 메시지")
    detail: Optional[str] = Field(None, description="상세 에러 정보")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "모델 로딩 실패",
                "detail": "Doc2Vec 모델 파일을 찾을 수 없습니다."
            }
        }


class HealthResponse(BaseModel):
    """서버 상태 응답"""
    status: str = Field(..., description="서버 상태 ('healthy' 또는 'unhealthy')")
    message: str = Field(..., description="상태 메시지")
    models_loaded: bool = Field(..., description="모델 로딩 여부")
    doc2vec_loaded: bool = Field(False, description="Doc2Vec 모델 로딩 여부")
    cnn_loaded: bool = Field(False, description="CNN 모델 로딩 여부")
    errors: Optional[List[str]] = Field(default_factory=list, description="에러 목록")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "message": "서버가 정상 작동 중입니다",
                "models_loaded": True,
                "doc2vec_loaded": True,
                "cnn_loaded": True,
                "errors": []
            }
        }
