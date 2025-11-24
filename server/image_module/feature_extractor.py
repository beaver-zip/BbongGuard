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

    def extract_embeddings(self, frames: List[Dict[str, Any]]) -> List[np.ndarray]:
        """
        프레임 리스트에서 CLIP 임베딩을 추출합니다. (병렬 처리용)
        """
        if not frames:
            return []

        logger.info(f"CLIP 임베딩 추출 시작: {len(frames)}장")
        
        try:
            # 1. 이미지 객체 변환 (OpenCV BGR -> PIL RGB)
            pil_images = []
            for f in frames:
                img_rgb = cv2.cvtColor(f['image'], cv2.COLOR_BGR2RGB)
                pil_images.append(Image.fromarray(img_rgb))

            # 2. CLIP 임베딩 (배치 처리)
            embeddings = self.clip_model.encode(pil_images, batch_size=32, convert_to_numpy=True)
            return list(embeddings)
            
        except Exception as e:
            logger.error(f"CLIP 임베딩 생성 실패: {e}")
            return [np.zeros(512) for _ in frames] # 실패 시 0 벡터 반환

    def extract_ocr(self, frames: List[Dict[str, Any]]) -> List[str]:
        """
        프레임 리스트에서 OCR 텍스트를 추출합니다. (병렬 처리용)
        """
        if not frames:
            return []

        logger.info(f"OCR 텍스트 추출 시작: {len(frames)}장")
        ocr_texts = []

        for i, frame in enumerate(frames):
            try:
                # OCR 수행
                ocr_result = self.ocr_reader.readtext(frame['image'], detail=0) # 텍스트만 추출
                ocr_text = " ".join(ocr_result)
                ocr_texts.append(ocr_text)
            except Exception as e:
                logger.warning(f"프레임 {frame['frame_id']} OCR 실패: {e}")
                ocr_texts.append("")
        
        return ocr_texts

    def extract(self, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        (Legacy) 순차적으로 특징 추출 (하위 호환성 유지)
        """
        embeddings = self.extract_embeddings(frames)
        ocr_texts = self.extract_ocr(frames)
        
        processed_frames = []
        for i, frame in enumerate(frames):
            processed_frame = frame.copy()
            del processed_frame['image']
            processed_frame['embedding'] = embeddings[i]
            processed_frame['ocr_text'] = ocr_texts[i]
            processed_frames.append(processed_frame)
            
        return processed_frames
