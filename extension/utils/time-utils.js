// time-utils.js - 시간 관련 유틸리티

/**
 * ISO 8601 Duration 문자열을 초 단위 정수로 변환합니다.
 * 예: "PT1H2M10S" -> 3730
 * @param {string} duration - ISO 8601 Duration 문자열
 * @returns {number} 초 단위 시간
 */
function parseISODuration(duration) {
  if (!duration) return 0;
  
  const match = duration.match(/PT(\d+H)?(\d+M)?(\d+S)?/);
  if (!match) return 0;

  const hours = (parseInt(match[1]) || 0);
  const minutes = (parseInt(match[2]) || 0);
  const seconds = (parseInt(match[3]) || 0);

  return hours * 3600 + minutes * 60 + seconds;
}
