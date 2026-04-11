"""
vision_utils.py — 비디오 프레임 추출 및 비전 모델 분석 유틸리티

[TODO]
이 파일의 두 함수를 구현하세요.
구현 순서: extract_key_frames → analyze_frame_with_vision_model
"""

import json
import os
import subprocess
import time
import base64
import requests
from typing import List, Dict

from app.config import CONFIG
from app.prompts import get_vision_prompt


def _get_video_duration(video_path: str) -> float:
    """ffprobe로 비디오 재생 시간(초)을 가져옵니다."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            video_path,
        ],
        capture_output=True,
        text=True,
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def extract_key_frames(
    video_path: str, output_dir: str, frames_per_minute: int = 1
) -> List[Dict]:
    """
    [TODO] 비디오에서 일정 간격으로 키 프레임을 추출합니다.

    요구사항:
    1. opencv-python-headless(cv2)를 사용하여 비디오를 열고 프레임을 추출하세요.
       - frames_per_minute 간격(초)으로 프레임을 추출합니다.
       - 추출된 프레임을 output_dir에 JPEG 파일로 저장하세요.
    2. 반환값은 {"timestamp": float(초), "frame_path": str} 형태의 딕셔너리 리스트입니다.

    힌트:
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = total_frames / fps  # 총 재생 시간(초)

        interval_sec = 60 / frames_per_minute  # 프레임 간격(초)
        timestamp = 0.0
        while timestamp < duration:
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ret, frame = cap.read()
            if ret:
                frame_path = os.path.join(output_dir, f"frame_{timestamp:.1f}.jpg")
                cv2.imwrite(frame_path, frame)
                # 결과 리스트에 추가 ...
            timestamp += interval_sec
        cap.release()

    Args:
        video_path (str): 비디오 파일 경로
        output_dir (str): 프레임 저장 디렉토리
        frames_per_minute (int): 분당 추출할 프레임 수 (기본값: 1)

    Returns:
        List[Dict]: [{"timestamp": 0.0, "frame_path": "app/frames/.../frame_0.0.jpg"}, ...]
    """

    # ---------------------------------------------------------
    # ffmpeg CLI 기반 프레임 추출 (AV1 등 모든 코덱 지원)
    # ---------------------------------------------------------

    result = []

    duration = _get_video_duration(video_path)
    print(f"[vision] Video duration: {duration:.1f}s")

    interval_sec = 60 / frames_per_minute
    timestamp = 0.0

    while timestamp < duration:
        frame_path = os.path.join(output_dir, f"frame_{timestamp:.1f}.jpg")
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(timestamp),
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-q:v",
                "2",
                frame_path,
            ],
            capture_output=True,
        )
        if proc.returncode == 0 and os.path.exists(frame_path):
            result.append({"timestamp": timestamp, "frame_path": frame_path})
        else:
            print(f"[vision] WARNING: Failed to extract frame at {timestamp:.1f}s")

        timestamp += interval_sec

    print(f"[vision] Extracted {len(result)} key frames")

    return result


def analyze_frame_with_vision_model(frame_path: str, timestamp: float) -> str:
    """
    [TODO] 프레임 이미지를 비전 모델에 전달하여 장면 설명을 생성합니다.

    요구사항:
    1. PROVIDER=local: Ollama의 moondream 모델을 사용하세요.
       - Ollama API의 images 파라미터에 base64 인코딩된 이미지를 전달합니다.
       - Ollama API 문서 확인: https://github.com/ollama/ollama/blob/main/docs/api.md
    2. PROVIDER=openai: GPT-4o Vision API를 사용하세요.
       - openai.chat.completions.create()에 image_url 또는 base64 이미지 전달
    3. 반환값은 해당 프레임의 장면 설명 문자열입니다.

    힌트 (로컬 Ollama):
        import base64, requests
        from app.config import OLLAMA_BASE, OLLAMA_VISION_MODEL

        with open(frame_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        response = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={
                "model": OLLAMA_VISION_MODEL,
                "prompt": f"[{timestamp:.1f}s] 이 인터뷰 영상 프레임에서 무슨 일이 일어나고 있는지 한국어로 간결하게 설명해주세요.",
                "images": [image_b64],
                "stream": False,
            },
        )
        return response.json()["response"]

    Args:
        frame_path (str): 분석할 프레임 이미지 경로
        timestamp (float): 해당 프레임의 타임스탬프(초)

    Returns:
        str: 프레임 장면 설명
    """
    # ---------------------------------------------------------
    # [TODO] 비전 모델 분석 로직 작성
    # 기본: Ollama moondream (PROVIDER=local)
    # 선택: GPT-4o Vision (PROVIDER=openai)
    # ---------------------------------------------------------

    with open(frame_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    prompt = get_vision_prompt(timestamp)

    if CONFIG.provider == "openai":
        from openai import OpenAI, RateLimitError

        client = OpenAI(api_key=CONFIG.openai_api_key)
        for attempt in range(5):
            try:
                resp = client.chat.completions.create(
                    model=CONFIG.openai_vision_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_b64}",
                                    },
                                },
                            ],
                        }
                    ],
                )
                return resp.choices[0].message.content
            except RateLimitError:
                wait = min(2**attempt * 5, 60)
                print(
                    f"[vision] Rate limit hit, retrying in {wait}s... ({attempt + 1}/5)"
                )
                time.sleep(wait)
        raise RuntimeError("OpenAI vision rate limit: 5회 재시도 후에도 실패")
    else:
        response = requests.post(
            f"{CONFIG.ollama_base}/api/generate",
            json={
                "model": CONFIG.ollama_vision_model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
            },
        )
        return response.json()["response"]
