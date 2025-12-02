import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import sys
import os
import numpy as np

# 프로젝트 루트 경로 추가 (모듈 import를 위해)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.image_module.image_analyzer import ImageAnalyzer
from server.image_module.schemas import ImageAnalysisRequest, Claim

class TestImageAnalyzer(unittest.TestCase):

    def setUp(self):
        """테스트 설정"""
        self.mock_request = ImageAnalysisRequest(
            video_id="test_video_id",
            claims=[Claim(claim_id="c1", claim_text="Test Claim", category="Test", importance="High")]
        )

    @patch('server.image_module.image_analyzer.vision.ImageAnnotatorClient')
    @patch('server.image_module.image_analyzer.FrameSampler')
    @patch('server.image_module.image_analyzer.requests.get')
    def test_analyze_flow(self, mock_get, mock_sampler_class, mock_vision_client):
        """전체 분석 흐름 테스트 (API 호출 Mocking)"""
        
        # 1. Vision Client Mock 설정
        mock_client_instance = mock_vision_client.return_value
        
        # Web Detection 결과 Mock
        mock_web_resp = MagicMock()
        mock_web_resp.web_detection.pages_with_matching_images = [
            MagicMock(url="http://fake-news.com/old-article", page_title="Old News")
        ]
        mock_web_resp.web_detection.best_guess_labels = [MagicMock(label="Fake Event")]
        mock_client_instance.web_detection.return_value = mock_web_resp

        # Annotate Image (Label/Text) 결과 Mock
        mock_annotate_resp = MagicMock()
        mock_annotate_resp.label_annotations = [MagicMock(description="Crowd"), MagicMock(description="Street")]
        mock_annotate_resp.text_annotations = [MagicMock(description="Shocking Truth")]
        mock_client_instance.annotate_image.return_value = mock_annotate_resp

        # 2. FrameSampler Mock 설정 (실제 영상 다운로드 방지)
        mock_sampler_instance = mock_sampler_class.return_value
        # 가짜 프레임 데이터 (검은 화면)
        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_sampler_instance.sample_frames.return_value = [
            {'frame_id': 0, 'timestamp': 1.0, 'image': dummy_frame},
            {'frame_id': 1, 'timestamp': 5.0, 'image': dummy_frame}
        ]

        # 3. Requests Mock (썸네일 다운로드 방지)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'fake_image_bytes'
        mock_get.return_value = mock_response

        # 4. 테스트 실행
        analyzer = ImageAnalyzer()
        
        # Async 함수 실행
        result = asyncio.run(analyzer.analyze(self.mock_request))

        # 5. 검증 (Assertion)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.modality, "image")
        
        # 요약문에 핵심 키워드가 포함되었는지 확인
        self.assertIn("재사용 감지", result.analysis_summary)
        self.assertIn("old-article", result.analysis_summary) # URL 확인
        self.assertIn("Crowd", result.analysis_summary) # 라벨 확인
        self.assertIn("Shocking Truth", result.analysis_summary) # OCR 텍스트 확인

        print("\n[테스트 결과 요약]")
        print(result.analysis_summary)

if __name__ == '__main__':
    unittest.main()