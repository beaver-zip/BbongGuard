"""하위 호환성을 위한 통합 임포트 파일

기존 코드에서 `from ..shared.rag_models import ...` 형태로
사용하던 부분의 호환성 유지
"""

# 텍스트 모듈
from .text_module import (
    Claim,
    Evidence,
    ClaimVerdict,
    Finding,
    TextModuleResult,
    TextAnalysisRequest,
)

# 멀티모달 통합
from .multimodal_result import (
    ModuleResult,
    FinalVerdict,
    MultiModalAnalysisResult,
)

# 하위 호환성을 위한 별칭
ModalityResult = TextModuleResult  # 기존 코드 호환용

__all__ = [
    # 텍스트 모듈
    'Claim',
    'Evidence',
    'ClaimVerdict',
    'Finding',
    'TextModuleResult',
    'TextAnalysisRequest',
    # 멀티모달
    'ModuleResult',
    'FinalVerdict',
    'MultiModalAnalysisResult',
    # 호환성
    'ModalityResult',
]
