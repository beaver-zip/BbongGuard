"""영상 프레임 샘플링 모듈"""

import cv2
import yt_dlp
import os
import tempfile
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from ..shared.schemas import VideoMeta

logger = logging.getLogger(__name__)

class FrameSampler:
    """YouTube 영상에서 프레임을 샘플링하는 클래스"""

    def __init__(self, max_frames: int = 60, sample_interval_sec: float = 1.0):
        """
        Args:
            max_frames: 최대 추출 프레임 수
            sample_interval_sec: 프레임 추출 간격 (초)
        """
        self.max_frames = max_frames
        self.sample_interval_sec = sample_interval_sec
        logger.info(f"FrameSampler 초기화 - 최대 {max_frames}프레임, {sample_interval_sec}초 간격")

    def get_stream_url(self, video_url: str) -> Optional[str]:
        """
        yt-dlp를 사용하여 스트리밍 URL을 추출합니다.
        """
        try:
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return info.get('url')
        except Exception as e:
            logger.error(f"스트리밍 URL 추출 실패: {e}")
            return None

    def sample_frames(self, video_meta: VideoMeta) -> List[Dict[str, Any]]:
        """
        영상의 0% ~ 90% 지점(키보드 0-9)에서 프레임을 샘플링합니다.
        스트리밍 방식을 사용하여 다운로드 없이 빠르게 처리합니다.
        """
        stream_url = self.get_stream_url(video_meta.url)
        if not stream_url:
            return []
            
        frames = []
        cap = cv2.VideoCapture(stream_url)
        
        if not cap.isOpened():
            logger.error(f"영상 스트림을 열 수 없습니다: {video_meta.url}")
            return []

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            
            logger.info(f"영상 정보: FPS={fps}, Total Frames={total_frames}, Duration={duration:.2f}s")
            
            # 0% ~ 90% 지점 (10개)
            target_positions = [i * 0.1 for i in range(10)]
            
            for i, pos in enumerate(target_positions):
                target_frame_idx = int(total_frames * pos)
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_idx)
                
                ret, frame = cap.read()
                if ret:
                    timestamp = target_frame_idx / fps if fps > 0 else 0
                    frame_data = {
                        'frame_id': i, # 0~9
                        'timestamp': timestamp,
                        'image': frame # BGR format
                    }
                    frames.append(frame_data)
                else:
                    logger.warning(f"프레임 읽기 실패: {target_frame_idx} ({pos*100}%)")
                    
            logger.info(f"프레임 샘플링 완료: {len(frames)}장 추출 (0-9 지점)")
            return frames
            
        except Exception as e:
            logger.error(f"프레임 샘플링 중 오류: {e}", exc_info=True)
            return []
            
        finally:
            cap.release()
