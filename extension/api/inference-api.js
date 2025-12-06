// inference-api.js - 추론 서버 통신 로직

// 추론 서버 URL 가져오기 (chrome.storage에서)
async function getInferenceServerUrl() {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(['inferenceServerUrl'], (result) => {
      if (result.inferenceServerUrl) {
        resolve(result.inferenceServerUrl);
      } else {
        // 기본값 (로컬 개발 환경)
        resolve('http://localhost:8000');
      }
    });
  });
}

// 추론 서버로 데이터 전송 및 분석 결과 받기
async function analyzeWithInferenceServer(videoData) {
  try {
    const serverUrl = await getInferenceServerUrl();
    const endpoint = `${serverUrl}/api/analyze-multimodal`; // [수정] 엔드포인트 변경

    // 서버로 전송할 데이터 구조화 (snake_case 적용)
    const payload = {
      video_id: videoData.videoId,
      title: videoData.title,
      description: videoData.description || "",
      comments: (videoData.comments || []).map(comment =>
        typeof comment === 'string' ? comment : comment.text
      ).slice(0, 100),
      duration_sec: videoData.durationSec || 0, // [New]
      // 추가 정보 (서버 로깅용)
      channel_title: videoData.channelTitle,
      views: parseInt(videoData.viewCount) || 0,
      thumbnail_url: videoData.thumbnailUrl
    };

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || `추론 서버 응답 오류 (${response.status})`);
    }

    const result = await response.json();
    const verdict = result.final_verdict;

    // 가짜뉴스 확률 매핑 (is_fake_news 기반)
    let probability = 0.1;
    if (verdict.is_fake_news) {
        probability = verdict.confidence_level === 'high' ? 0.95 : 0.8;
    } else {
        probability = verdict.confidence_level === 'high' ? 0.05 : 0.2;
    }

    // 응답 데이터 검증 및 정규화
    return {
      probability: probability,
      evidence: verdict.key_evidence && verdict.key_evidence.length > 0 ? verdict.key_evidence : [verdict.overall_reasoning],
      textSources: verdict.text_sources || [], // [New] 텍스트 출처
      details: verdict
    };

  } catch (error) {
    console.error('추론 서버 통신 실패:', error);

    // 네트워크 오류인 경우
    if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
      throw new Error('추론 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.');
    }

    throw error;
  }
}

// 썸네일 이미지를 base64로 변환 (필요 시 사용)
async function fetchImageAsBase64(imageUrl) {
  try {
    const response = await fetch(imageUrl);
    const blob = await response.blob();

    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });

  } catch (error) {
    console.error('이미지를 base64로 변환하는 데 실패:', error);
    return null;
  }
}

// 서버 상태 확인 (헬스체크)
async function checkServerHealth() {
  try {
    const serverUrl = await getInferenceServerUrl();
    const endpoint = `${serverUrl}/health`;

    const response = await fetch(endpoint, { method: 'GET' });

    return response.ok;

  } catch (error) {
    console.error('서버 상태 확인 실패:', error);
    return false;
  }
}
