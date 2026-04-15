"""
ingest/chunking.py — 전사 세그먼트를 embedding window 기준 청크로 분할.
"""

from typing import Dict, List

from langsmith import traceable

from ..config import EmbeddingCfg, get_stage_config


@traceable(name="chunk")
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
