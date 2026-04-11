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
