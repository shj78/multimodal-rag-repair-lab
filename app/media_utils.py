"""
media_utils.py — 미디어 세그먼트 처리 및 임베딩 유틸리티

[TODO]
구현 순서: segment_transcript → get_text_embedding → combine_multimodal_context
"""

import time
import requests
from typing import List, Dict, Any

from app.config import CONFIG


def segment_transcript(
    segments: List[Dict],
    window_seconds: float = CONFIG.chunk_window_seconds,
    overlap_seconds: float = CONFIG.chunk_overlap_seconds,
) -> List[Dict]:
    """
    전사 세그먼트를 시간 윈도우 기반으로 청킹합니다.

    overlap_seconds > 0이면 슬라이딩 윈도우 방식으로 경계 발화가
    양쪽 청크에 포함되어 잘림을 방지합니다.

    Args:
        segments (List[Dict]): transcribe_audio() 반환값
        window_seconds (float): 청크 시간 윈도우 크기(초)
        overlap_seconds (float): 윈도우 간 겹침(초)

    Returns:
        List[Dict]: [{"start": 0.0, "end": 30.0, "text": "...", "chunk_index": 0}, ...]
    """
    if not segments:
        return []

    step = window_seconds - overlap_seconds
    chunks = []

    window_start = segments[0]["start"]
    max_end = segments[-1]["end"]

    while window_start < max_end:
        window_end = window_start + window_seconds
        texts = []

        for seg in segments:
            if seg["end"] > window_start and seg["start"] < window_end:
                texts.append(seg["text"].strip())

        if texts:
            actual_end = min(window_end, max_end)
            chunks.append(
                {
                    "start": window_start,
                    "end": actual_end,
                    "text": " ".join(texts),
                    "chunk_index": len(chunks),
                }
            )

        window_start += step

    return chunks


def get_text_embedding(text: str) -> List[float]:
    """
    [TODO] 텍스트의 벡터 임베딩을 생성합니다.

    요구사항:
    1. PROVIDER=local: Ollama의 nomic-embed-text 모델을 사용하세요.
       - Ollama Embeddings API 조사: POST /api/embeddings
    2. PROVIDER=openai: OpenAI Embeddings API를 사용하세요.
       - text-embedding-3-small 모델 사용
    3. 반환값은 float 리스트(벡터)입니다. 차원은 config.py의 EMBEDDING_DIM을 확인하세요.

    힌트 (로컬 Ollama):
        from app.config import OLLAMA_BASE, OLLAMA_EMBED_MODEL
        response = requests.post(
            f"{OLLAMA_BASE}/api/embeddings",
            json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
        )
        return response.json()["embedding"]

    Args:
        text (str): 임베딩할 텍스트

    Returns:
        List[float]: 임베딩 벡터
    """

    if CONFIG.provider == "openai":
        from openai import OpenAI, RateLimitError

        client = OpenAI(api_key=CONFIG.openai_api_key)
        for attempt in range(5):
            try:
                resp = client.embeddings.create(
                    model=CONFIG.openai_embedding_model,
                    input=text,
                    dimensions=CONFIG.embedding_dim,
                )
                return resp.data[0].embedding
            except RateLimitError as e:
                wait = min(2**attempt, 10)
                print(
                    f"[embedding] Rate limit hit, retrying in {wait}s... ({attempt + 1}/5)"
                )
                time.sleep(wait)
        raise RuntimeError("OpenAI embedding rate limit: 5회 재시도 후에도 실패")
    else:
        response = requests.post(
            f"{CONFIG.ollama_base}/api/embeddings",
            json={"model": CONFIG.ollama_embed_model, "prompt": text},
        )
        return response.json()["embedding"]


def combine_multimodal_context(
    transcript_chunks: List[Dict],
    frame_analyses: List[Dict],
    start: float,
    end: float,
) -> str:
    """
    [TODO] 전사 청크와 해당 시간 구간의 프레임 분석 결과를 조합합니다.

    요구사항:
    1. start~end 시간 구간의 전사 텍스트를 합칩니다.
    2. 동일 구간에 해당하는 frame_analyses의 description을 타임스탬프와 함께 추가합니다.
    3. 반환값은 임베딩 또는 LLM 컨텍스트로 사용될 단일 문자열입니다.
    4. frame_analyses가 비어 있으면 (오디오 전용 파일) 전사 텍스트만 반환하세요.

    예시 반환값:
        "[전사] 사용자가 결제 버튼을 찾기 어려웠다고 말했습니다.
         [비전 02:14] 사용자가 결제 화면을 바라보고 있음."

    Args:
        transcript_chunks (List[Dict]): segment_transcript() 반환값 중 해당 구간 청크
        frame_analyses (List[Dict]): [{"timestamp": float, "description": str}, ...]
        start (float): 구간 시작 시간(초)
        end (float): 구간 종료 시간(초)

    Returns:
        str: 멀티모달 컨텍스트 문자열
    """
    # ---------------------------------------------------------
    # [TODO] 멀티모달 컨텍스트 조합 로직 작성
    # ---------------------------------------------------------
    transcript_text = " ".join(chunk["text"] for chunk in transcript_chunks)

    if not frame_analyses:
        return f"[전사] {transcript_text}"

    relevant_frames = [f for f in frame_analyses if start <= f["timestamp"] < end]
    parts = [f"[전사] {transcript_text}"]
    for frame in relevant_frames:
        ts = frame["timestamp"]
        mm_ss = f"{int(ts // 60):02d}:{int(ts % 60):02d}"
        parts.append(f"[비전 {mm_ss}] {frame['description']}")

    return "\n".join(parts)
