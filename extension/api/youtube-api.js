// youtube-api.js - YouTube Data API v3 호출 로직

// TODO: API 키는 .env에서 관리하고, 실제로는 백엔드 프록시 서버를 통해 호출하는 것이 보안상 좋습니다.
// 현재는 Chrome Extension에서 직접 호출하는 구조로 작성되었습니다.

const YOUTUBE_API_BASE_URL = 'https://www.googleapis.com/youtube/v3';

// API 키 가져오기 (chrome.storage에서)
async function getApiKey() {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(['youtubeApiKey'], (result) => {
      if (result.youtubeApiKey) {
        resolve(result.youtubeApiKey);
      } else {
        reject(new Error('YouTube API 키가 설정되지 않았습니다. 확장프로그램 설정 페이지에서 API 키를 입력해주세요.'));
      }
    });
  });
}

// 영상 정보 가져오기
async function getVideoInfo(videoId) {
  try {
    const apiKey = await getApiKey();
    const url = `${YOUTUBE_API_BASE_URL}/videos?part=snippet,statistics,contentDetails&id=${videoId}&key=${apiKey}`;

    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok) {
      const errorMessage = data.error?.message || 'YouTube API 호출 실패';
      const errorCode = response.status;

      // HTTP 상태 코드별 구체적인 메시지
      if (errorCode === 400) {
        throw new Error(`잘못된 요청: ${errorMessage} (API 키 형식을 확인해주세요)`);
      } else if (errorCode === 403) {
        throw new Error(`권한 없음: ${errorMessage} (YouTube Data API v3가 활성화되어 있는지 확인해주세요)`);
      } else if (errorCode === 429) {
        throw new Error(`할당량 초과: 일일 YouTube API 할당량을 초과했습니다`);
      } else {
        throw new Error(`YouTube API 오류 (${errorCode}): ${errorMessage}`);
      }
    }

    if (!data.items || data.items.length === 0) {
      throw new Error('영상을 찾을 수 없습니다.');
    }

    const video = data.items[0];
    return {
      videoId: videoId,
      title: video.snippet.title,
      description: video.snippet.description,
      channelTitle: video.snippet.channelTitle,
      channelId: video.snippet.channelId,
      publishedAt: video.snippet.publishedAt,
      thumbnailUrl: video.snippet.thumbnails.high?.url || video.snippet.thumbnails.default.url,
      viewCount: video.statistics.viewCount,
      likeCount: video.statistics.likeCount,
      commentCount: video.statistics.commentCount,
      duration: video.contentDetails.duration,
      tags: video.snippet.tags || []
    };

  } catch (error) {
    console.error('영상 정보 가져오기 실패:', error);
    throw error;
  }
}

// 댓글 가져오기
async function getVideoComments(videoId, maxResults = 20) {
  try {
    const apiKey = await getApiKey();
    const url = `${YOUTUBE_API_BASE_URL}/commentThreads?part=snippet&videoId=${videoId}&maxResults=${maxResults}&order=relevance&key=${apiKey}`;

    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok) {
      // 댓글이 비활성화된 경우 등
      console.warn('댓글을 가져올 수 없습니다:', data.error?.message);
      return [];
    }

    const comments = data.items?.map(item => ({
      text: item.snippet.topLevelComment.snippet.textDisplay,
      author: item.snippet.topLevelComment.snippet.authorDisplayName,
      likeCount: item.snippet.topLevelComment.snippet.likeCount,
      publishedAt: item.snippet.topLevelComment.snippet.publishedAt
    })) || [];

    return comments;

  } catch (error) {
    console.error('댓글 가져오기 실패:', error);
    return []; // 댓글을 못 가져와도 전체 분석은 계속 진행
  }
}

// 관련 영상 가져오기
async function getRelatedVideos(videoId, maxResults = 9) {
  try {
    const apiKey = await getApiKey();
    const url = `${YOUTUBE_API_BASE_URL}/search?part=snippet&relatedToVideoId=${videoId}&type=video&maxResults=${maxResults}&key=${apiKey}`;

    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok) {
      console.warn('관련 영상을 가져올 수 없습니다:', data.error?.message);
      return [];
    }

    const relatedVideos = data.items?.map(item => ({
      videoId: item.id.videoId,
      title: item.snippet.title,
      description: item.snippet.description || "",
      channelTitle: item.snippet.channelTitle,
      thumbnailUrl: item.snippet.thumbnails.default.url
    })) || [];

    return relatedVideos;

  } catch (error) {
    console.error('관련 영상 가져오기 실패:', error);
    return [];
  }
}

// 채널 정보 가져오기
async function getChannelInfo(channelId) {
  try {
    const apiKey = await getApiKey();
    const url = `${YOUTUBE_API_BASE_URL}/channels?part=snippet,statistics&id=${channelId}&key=${apiKey}`;

    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error?.message || '채널 정보를 가져올 수 없습니다.');
    }

    if (!data.items || data.items.length === 0) {
      throw new Error('채널을 찾을 수 없습니다.');
    }

    const channel = data.items[0];
    return {
      channelId: channelId,
      title: channel.snippet.title,
      description: channel.snippet.description,
      subscriberCount: channel.statistics.subscriberCount,
      videoCount: channel.statistics.videoCount,
      viewCount: channel.statistics.viewCount,
      thumbnailUrl: channel.snippet.thumbnails.default.url
    };

  } catch (error) {
    console.error('채널 정보 가져오기 실패:', error);
    return null;
  }
}
