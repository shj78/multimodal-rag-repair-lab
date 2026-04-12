"""
correction_utils.py — Vision-guided 전사 교정

Vision 분석(frame_analyses) 결과를 근거로 Whisper 전사 세그먼트의
코드 용어·함수명·변수명을 교정한다.

- 프레임 타임스탬프가 세그먼트 구간과 겹치는 경우만 교정.
- 프레임이 없는 구간은 원문 유지.
- 교정 실패 시 경고 로그 후 원문 유지 (파이프라인 중단 없음).
"""

import logging

import requests
from openai import OpenAI

from .config import CorrectionCfg, get_stage_config
from .prompts import get_correction_prompt

logger = logging.getLogger(__name__)


def correct_transcription_with_vision(
    segments: list[dict],
    frame_analyses: list[dict],
    cfg: CorrectionCfg | None = None,
) -> list[dict]:
    """Vision 분석 결과를 근거로 전사 세그먼트를 교정한다.

    Args:
        segments: transcribe_audio() 반환값 [{start, end, text}, ...]
        frame_analyses: [{timestamp, description}, ...] — vision 분석 결과
        cfg: CorrectionCfg. None이면 get_stage_config().correction 사용.

    Returns:
        교정된 segments. 원본 구조({start, end, text}) 유지, text만 수정됨.
    """
    cfg = cfg or get_stage_config().correction
    if not cfg.enabled or not frame_analyses:
        return segments

    corrected = []
    for seg in segments:
        frame = _find_overlapping_frame(seg["start"], seg["end"], frame_analyses)
        if frame is None:
            corrected.append(seg)
            continue
        try:
            corrected_text = _call_llm_correction(
                seg["text"], frame["description"], cfg
            )
            corrected.append({**seg, "text": corrected_text})
        except Exception as e:
            logger.warning(
                "교정 실패 (원문 유지) seg=[%.1f~%.1f]: %s",
                seg["start"],
                seg["end"],
                e,
            )
            corrected.append(seg)
    return corrected


def _find_overlapping_frame(
    start: float, end: float, frame_analyses: list[dict]
) -> dict | None:
    """세그먼트 구간 [start, end]와 타임스탬프가 겹치는 첫 번째 프레임을 반환한다."""
    for frame in frame_analyses:
        if start <= frame["timestamp"] <= end:
            return frame
    return None


def _call_llm_correction(
    transcription_text: str, frame_description: str, cfg: CorrectionCfg
) -> str:
    """LLM을 호출하여 전사 텍스트를 교정하고 교정된 텍스트를 반환한다."""
    prompt = get_correction_prompt(frame_description, transcription_text)

    if cfg.provider == "openai":
        client = OpenAI(api_key=cfg.openai_api_key)
        resp = client.chat.completions.create(
            model=cfg.openai_chat_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        return resp.choices[0].message.content.strip()

    resp = requests.post(
        f"{cfg.ollama_base}/api/chat",
        json={
            "model": cfg.ollama_chat_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        },
    )
    return resp.json()["message"]["content"].strip()
