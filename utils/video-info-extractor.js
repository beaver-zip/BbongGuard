// video-info-extractor.js - 영상 정보 추출 유틸리티

// YouTube URL에서 video ID 추출
function extractVideoId(url) {
  try {
    const urlObj = new URL(url);

    // youtube.com/watch?v=VIDEO_ID 형식
    if (urlObj.hostname.includes('youtube.com')) {
      return urlObj.searchParams.get('v');
    }

    // youtu.be/VIDEO_ID 형식
    if (urlObj.hostname === 'youtu.be') {
      return urlObj.pathname.slice(1);
    }

    return null;
  } catch (error) {
    console.error('URL 파싱 실패:', error);
    return null;
  }
}

// 현재 탭의 URL에서 video ID 추출
async function getCurrentVideoId() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs && tabs.length > 0) {
        const videoId = extractVideoId(tabs[0].url);
        resolve(videoId);
      } else {
        resolve(null);
      }
    });
  });
}

// 텍스트 전처리 (HTML 태그 제거, 특수문자 정리 등)
function sanitizeText(text) {
  if (!text) return '';

  return text
    .replace(/<[^>]*>/g, '') // HTML 태그 제거
    .replace(/&nbsp;/g, ' ') // &nbsp; 제거
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .trim();
}

// 댓글 텍스트 요약 (길이 제한)
function truncateText(text, maxLength = 500) {
  if (!text || text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

// 영상 데이터 유효성 검증
function validateVideoData(videoData) {
  const required = ['videoId', 'title', 'channelTitle'];

  for (const field of required) {
    if (!videoData[field]) {
      throw new Error(`필수 필드 누락: ${field}`);
    }
  }

  return true;
}

// 추론 서버 응답 검증
function validateInferenceResponse(response) {
  if (typeof response !== 'object' || response === null) {
    throw new Error('잘못된 응답 형식');
  }

  if (!('probability' in response) && !('fakeProbability' in response)) {
    throw new Error('확률 정보가 없습니다');
  }

  const probability = response.probability ?? response.fakeProbability;

  if (typeof probability !== 'number' || probability < 0 || probability > 100) {
    throw new Error('확률 값이 유효하지 않습니다');
  }

  return true;
}

// 숫자 포맷팅 (조회수, 좋아요 수 등)
function formatNumber(num) {
  if (!num) return '0';

  const number = parseInt(num);

  if (number >= 1000000000) {
    return (number / 1000000000).toFixed(1) + 'B';
  }
  if (number >= 1000000) {
    return (number / 1000000).toFixed(1) + 'M';
  }
  if (number >= 1000) {
    return (number / 1000).toFixed(1) + 'K';
  }

  return number.toLocaleString();
}

// 날짜 포맷팅
function formatDate(dateString) {
  if (!dateString) return '';

  const date = new Date(dateString);
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
}
