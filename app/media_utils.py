import time
import requests
from typing import List, Dict, Any

from langsmith import traceable

from app.config import EmbeddingCfg, get_stage_config


def segment_transcript(
    segments: List[Dict],
    cfg: EmbeddingCfg | None = None,
) -> List[Dict]:
    cfg = cfg or get_stage_config().embedding
    if not segments:
        return []

    window_seconds = cfg.chunk_window_seconds
    overlap_seconds = cfg.chunk_overlap_seconds
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


@traceable(name="query_embedding", run_type="tool")
def get_text_embedding(text: str, cfg: EmbeddingCfg | None = None) -> List[float]:
    cfg = cfg or get_stage_config().embedding
    if cfg.provider == "openai":
        from openai import OpenAI, RateLimitError

        client = OpenAI(api_key=cfg.openai_api_key)
        for attempt in range(5):
            try:
                resp = client.embeddings.create(
                    model=cfg.openai_embedding_model,
                    input=text,
                    dimensions=cfg.embedding_dim,
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
            f"{cfg.ollama_base}/api/embeddings",
            json={"model": cfg.ollama_embed_model, "prompt": text},
        )
        return response.json()["embedding"]


def combine_multimodal_context(
    transcript_chunks: List[Dict],
    frame_analyses: List[Dict],
    start: float,
    end: float,
) -> str:
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
