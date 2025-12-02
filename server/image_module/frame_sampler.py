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
    """다운로드 기반의 안정적인 프레임 샘플러"""

    def __init__(self, max_frames: int = 5, sample_interval_sec: float = 1.0):
        self.max_frames = max_frames

    def sample_frames(self, video_meta: VideoMeta) -> List[Dict[str, Any]]:
        video_url = video_meta.url
        frames = []
        temp_video_path = None

        try:
            # 1. 임시 파일로 영상 다운로드 (최저 화질로 빠르게)
            fd, temp_video_path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
            os.remove(temp_video_path)

            ydl_opts = {
                'format': 'worst[ext=mp4]', # 가장 낮은 화질 (분석용으로 충분)
                'outtmpl': temp_video_path,
                'quiet': True,
                'no_warnings': True,
            }
            
            logger.info("영상 다운로드 중 (Frame 추출용)...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            if not os.path.exists(temp_video_path):
                logger.error("영상 다운로드 실패")
                return []

            # 2. OpenCV로 프레임 추출
            cap = cv2.VideoCapture(temp_video_path)
            if not cap.isOpened():
                return []

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # 0% ~ 90% 지점 균등 샘플링
            for i in range(self.max_frames):
                pos = i / self.max_frames
                target_frame = int(total_frames * pos)
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                
                ret, frame = cap.read()
                if ret:
                    timestamp = target_frame / fps if fps > 0 else 0
                    frames.append({
                        'frame_id': i,
                        'timestamp': timestamp,
                        'image': frame
                    })
            
            cap.release()
            logger.info(f"프레임 추출 완료: {len(frames)}장")
            return frames

        except Exception as e:
            logger.error(f"프레임 샘플링 오류: {e}")
            return []
        finally:
            # 임시 파일 삭제
            if temp_video_path and os.path.exists(temp_video_path):
                try:
                    os.remove(temp_video_path)
                except:
                    pass