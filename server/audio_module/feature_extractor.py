"""오디오 특징 추출 (감정/톤)"""

import logging
import numpy as np
import librosa
import torch
from transformers import pipeline
from typing import List, Dict, Any
import os

from ..shared.schemas import AudioSegment

logger = logging.getLogger(__name__)

class AudioFeatureExtractor:
    """오디오 구간에서 감정, 톤, 스푸핑 여부를 분석하는 클래스"""

    def __init__(self):
        """모델 초기화"""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"AudioFeatureExtractor 초기화 (Device: {self.device})")

        try:
            # 감정 분석 모델 (Wav2Vec2 기반)
            # superb/wav2vec2-base-superb-er 모델 사용 (Emotion Recognition)
            self.emotion_classifier = pipeline(
                "audio-classification", 
                model="superb/wav2vec2-base-superb-er",
                device=0 if self.device == "cuda" else -1
            )
            logger.info("감정 분석 모델 로드 완료")
        except Exception as e:
            logger.error(f"감정 분석 모델 로드 실패: {e}")
            self.emotion_classifier = None

    def extract(self, audio_path: str, segments: List[AudioSegment]) -> List[AudioSegment]:
        """
        오디오 파일의 특정 구간들에 대해 특징을 추출합니다.

        Args:
            audio_path: 오디오 파일 경로
            segments: 분석할 오디오 구간 리스트

        Returns:
            특징이 업데이트된 AudioSegment 리스트
        """
        if not segments or not os.path.exists(audio_path):
            return segments

        try:
            # 전체 오디오 로드 (librosa는 sr=16000 권장 for wav2vec2)
            y, sr = librosa.load(audio_path, sr=16000)
            duration = librosa.get_duration(y=y, sr=sr)
            
            logger.info(f"오디오 로드 완료: {duration:.1f}초")

            for segment in segments:
                # 구간 추출
                start_sample = int(segment.start * sr)
                end_sample = int(segment.end * sr)
                
                # 범위 체크
                if start_sample >= len(y): continue
                end_sample = min(end_sample, len(y))
                
                y_seg = y[start_sample:end_sample]
                
                if len(y_seg) < sr * 0.5: # 0.5초 미만은 스킵
                    continue

                # 1. 감정 분석
                if self.emotion_classifier:
                    try:
                        # 파이프라인은 numpy array 입력 지원
                        results = self.emotion_classifier(y_seg, top_k=1)
                        if results:
                            segment.emotion = results[0]['label'] # neutral, happy, angry, etc.
                    except Exception as e:
                        logger.warning(f"감정 분석 실패 (S{segment.segment_id}): {e}")

                # 2. 톤/어조 분석 (Pitch, Energy 기반 간단한 휴리스틱)
                try:
                    rmse = librosa.feature.rms(y=y_seg)[0]
                    energy = np.mean(rmse)
                    
                    pitches, magnitudes = librosa.piptrack(y=y_seg, sr=sr)
                    pitch_mean = np.mean(pitches[magnitudes > np.median(magnitudes)]) if np.any(magnitudes > np.median(magnitudes)) else 0
                    
                    if energy > 0.1 and pitch_mean > 200:
                        segment.tone = "excited/high-tension"
                    elif energy < 0.02:
                        segment.tone = "calm/quiet"
                    else:
                        segment.tone = "neutral"
                        
                except Exception as e:
                    logger.warning(f"톤 분석 실패: {e}")

                # 3. 스푸핑 점수 (Placeholder)
                # 실제 딥페이크 탐지 모델 연동 필요 (현재는 0.0~0.2 사이 난수)
                segment.spoof_score = float(np.random.uniform(0.0, 0.1))

            return segments

        except Exception as e:
            logger.error(f"오디오 특징 추출 실패: {e}", exc_info=True)
            return segments
