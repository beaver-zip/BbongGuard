import requests
import json
import time
import yt_dlp

# ==========================================
# 1. 분석하고 싶은 유튜브 URL
# ==========================================
# TARGET_URL = "https://www.youtube.com/watch?v=QN45xosPsw4" 
TARGET_URL = "https://www.youtube.com/watch?v=GrlANJfluvM"

# 서버 API 주소
API_URL = "http://127.0.0.1:8000/api/analyze-multimodal"

def get_video_metadata(url):
    """
    yt-dlp를 사용하여 실제 영상 정보를 가져옵니다.
    """
    print(f"📥 [Client] 영상 정보 추출 중... ({url})")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True, # 영상 다운로드는 안 함 (정보만 추출)
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            return {
                "video_id": info.get('id'),
                "title": info.get('title'),
                "description": info.get('description', ''),
                "duration_sec": info.get('duration', 0),
                # 댓글은 yt-dlp로 가져오기 느리므로 테스트에선 생략하거나 임의값 사용
                "comments": [], 
                # 자막(transcript)은 비워두면 서버가 알아서 다시 추출합니다.
                "transcript": "" 
            }
    except Exception as e:
        print(f"❌ 영상 정보 추출 실패: {e}")
        return None

def run_test():
    # 1. 실제 영상 정보 가져오기
    video_data = get_video_metadata(TARGET_URL)
    
    if not video_data:
        return

    print("\n" + "="*50)
    print(f"🎬 분석 대상: {video_data['title']}")
    print(f"🆔 Video ID: {video_data['video_id']}")
    print("="*50 + "\n")

    print(f"📡 [BbongGuard] 서버에 분석 요청 전송...")
    print("⏳ 분석 중입니다... (Text, Image, Audio 모듈 동시 가동)")
    print("   (영상 길이에 따라 30초 ~ 2분 정도 소요될 수 있습니다)")

    try:
        start_time = time.time()
        # 서버 요청 (타임아웃을 넉넉하게 180초로 설정)
        response = requests.post(API_URL, json=video_data, timeout=180)
        end_time = time.time()

        if response.status_code == 200:
            result = response.json()
            verdict = result['final_verdict']
            
            print("\n" + "█"*50)
            print("✅ 분석 완료! 결과 리포트")
            print("█"*50)
            
            print(f"\n[최종 판결]")
            print(f"▶ 결과: {verdict['recommendation']}")
            print(f"▶ 신뢰도: {verdict['confidence_level']}")
            print(f"▶ 종합 판단: {verdict['overall_reasoning']}")
            
            print("\n" + "-"*30)
            print("[모듈별 상세 근거]")
            print("-"*30)
            print(f"📝 텍스트(팩트체크): {verdict['text_analysis_summary']}")
            print(f"🖼️ 이미지(재사용/조작): {verdict['image_analysis_summary']}")
            print(f"🔊 오디오(낚시/불일치): {verdict['audio_analysis_summary']}")
            
            print(f"\n⏱ 총 소요 시간: {end_time - start_time:.2f}초")
            
        else:
            print(f"❌ 서버 오류 발생: {response.status_code}")
            print(f"응답 내용: {response.text}")

    except requests.exceptions.ConnectionError:
        print("❌ 연결 실패: 서버가 실행 중인지 확인하세요.")
        print("   (터미널에서 'uvicorn server.main:app --reload' 실행 필요)")
    except Exception as e:
        print(f"❌ 에러 발생: {e}")

if __name__ == "__main__":
    run_test()