"""상세 로깅 유틸리티"""

import logging
import json
import os
import functools
import time
from datetime import datetime
from typing import Any, Callable
import inspect

# 로거 설정
logger = logging.getLogger("detailed_logger")
logger.setLevel(logging.INFO)

# 로그 디렉토리 설정
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def _json_serializable(obj):
    """JSON 직렬화 보조 함수"""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)

def log_execution(module_name: str, step_name: str):
    """
    함수 실행의 입력, 출력, 소요 시간을 JSON 파일로 로깅하는 데코레이터
    
    Args:
        module_name: 모듈 이름 (text, image, audio, main 등)
        step_name: 단계 이름 (extract, analyze, summarize 등)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 인자 캡처 (self 제외)
            bound_args = inspect.signature(func).bind(*args, **kwargs)
            bound_args.apply_defaults()
            inputs = {k: v for k, v in bound_args.arguments.items() if k != 'self'}
            
            # video_id 추출 시도 (파일명에 사용)
            video_id = "unknown"
            if 'video_meta' in inputs and hasattr(inputs['video_meta'], 'video_id'):
                video_id = inputs['video_meta'].video_id
            elif 'request' in inputs and hasattr(inputs['request'], 'video_id'):
                video_id = inputs['request'].video_id
            elif 'video_id' in inputs:
                video_id = inputs['video_id']
                
            log_entry = {
                "timestamp": timestamp,
                "module": module_name,
                "step": step_name,
                "function": func.__name__,
                "inputs": inputs,
                "status": "started"
            }
            
            # 시작 로그 (필요시)
            # _save_log(video_id, log_entry) 

            try:
                result = await func(*args, **kwargs)
                
                execution_time = time.time() - start_time
                log_entry.update({
                    "status": "success",
                    "execution_time_ms": execution_time * 1000,
                    "outputs": result
                })
                
                _save_log(video_id, log_entry)
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                log_entry.update({
                    "status": "error",
                    "execution_time_ms": execution_time * 1000,
                    "error": str(e)
                })
                _save_log(video_id, log_entry)
                raise e
                
        # 동기 함수 지원을 위한 처리 (필요시 추가 구현, 현재는 async만 가정)
        return wrapper
    return decorator

def _save_log(video_id: str, entry: dict):
    """로그를 파일에 추가 (Append 모드)"""
    try:
        # 날짜별 또는 비디오별 파일 생성
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{video_id}_{date_str}.json"
        filepath = os.path.join(LOG_DIR, filename)
        
        # 기존 로그 읽기
        logs = []
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    logs = json.load(f)
                    if not isinstance(logs, list):
                        logs = [logs]
                except:
                    logs = []
        
        logs.append(entry)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False, default=_json_serializable)
            
    except Exception as e:
        print(f"로그 저장 실패: {e}")
