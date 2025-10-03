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
    const endpoint = `${serverUrl}/api/analyze`;

    // 서버로 전송할 데이터 구조화
    const payload = {
      videoId: videoData.videoId,
      title: videoData.title,
      description: videoData.description,
      channelTitle: videoData.channelTitle,
      channelId: videoData.channelId,
      publishedAt: videoData.publishedAt,
      viewCount: videoData.viewCount,
      likeCount: videoData.likeCount,
      thumbnailUrl: videoData.thumbnailUrl,
      comments: videoData.comments?.slice(0, 100) || [], // 최대 100개 댓글
      relatedVideos: videoData.relatedVideos || [],
      tags: videoData.tags || []
    };

    // TODO: 썸네일 이미지를 base64로 인코딩하여 전송하는 로직 추가 가능
    // 현재는 썸네일 URL만 전송

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `추론 서버 응답 오류 (${response.status})`);
    }

    const result = await response.json();

    // 응답 데이터 검증 및 정규화
    return {
      probability: result.fakeProbability ?? result.probability ?? 0,
      evidence: result.evidence || [],
      details: result.details || null
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
