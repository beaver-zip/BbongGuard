import logging
import numpy as np
import torch
import cv2
from PIL import Image
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import easyocr

from ..config import Config

logger = logging.getLogger(__name__)

class ImageFeatureExtractor:
    """이미지에서 시각적 특징(CLIP)과 텍스트(OCR)를 추출하는 클래스"""

    def __init__(self):
        """모델 초기화"""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"ImageFeatureExtractor 초기화 (Device: {self.device})")

        # 1. CLIP 모델 로드 (이미지 임베딩용)
        try:
            # 이미지 인코딩을 위해 기본 CLIP 모델 사용 (multilingual은 텍스트용)
            # clip-ViT-B-32-multilingual-v1은 clip-ViT-B-32의 이미지 임베딩과 정렬됨
            self.clip_model = SentenceTransformer('clip-ViT-B-32', device=self.device)
            logger.info("CLIP 모델(Image) 로드 완료")
        except Exception as e:
            logger.error(f"CLIP 모델 로드 실패: {e}")
            raise

        # 2. OCR 엔진 로드 (EasyOCR)
        try:
            # GPU 메모리 부족 시 gpu=False로 설정 고려
            self.ocr_reader = easyocr.Reader(['ko', 'en'], gpu=(self.device == "cuda"))
            logger.info("OCR 엔진 로드 완료")
        except Exception as e:
            logger.error(f"OCR 엔진 로드 실패: {e}")
            raise

    def extract(self, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        프레임 리스트에서 특징을 추출합니다.

        Args:
            frames: FrameSampler가 반환한 프레임 리스트
                   [{'frame_id':..., 'timestamp':..., 'image': np.ndarray}]

        Returns:
            특징이 추가된 프레임 리스트
            [{..., 'embedding': np.ndarray, 'ocr_text': str}]
        """
        if not frames:
            return []

        logger.info(f"특징 추출 시작: {len(frames)}장")
        processed_frames = []

        # 1. 이미지 객체 변환 (OpenCV BGR -> PIL RGB)
        pil_images = []
        for f in frames:
            img_rgb = cv2.cvtColor(f['image'], cv2.COLOR_BGR2RGB)
            pil_images.append(Image.fromarray(img_rgb))

        # 2. CLIP 임베딩 (배치 처리)
        try:
            embeddings = self.clip_model.encode(pil_images, batch_size=32, convert_to_numpy=True)
        except Exception as e:
            logger.error(f"CLIP 임베딩 생성 실패: {e}")
            return []

        # 3. OCR 수행 (순차 처리)
        for i, frame in enumerate(frames):
            try:
                # OCR 수행
                ocr_result = self.ocr_reader.readtext(frame['image'], detail=0) # 텍스트만 추출
                ocr_text = " ".join(ocr_result)
                
                # 결과 저장
                processed_frame = frame.copy()
                del processed_frame['image']  # 메모리 절약을 위해 원본 이미지는 제거 (필요시 유지)
                
                processed_frame['embedding'] = embeddings[i]
                processed_frame['ocr_text'] = ocr_text
                
                processed_frames.append(processed_frame)
                
            except Exception as e:
                logger.warning(f"프레임 {frame['frame_id']} 처리 중 오류: {e}")
                continue

        logger.info(f"특징 추출 완료: {len(processed_frames)}장")
        return processed_frames
