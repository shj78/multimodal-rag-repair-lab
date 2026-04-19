"""
ingest/chunking.py — 전사 세그먼트를 청크로 분할.

chunking_strategy에 따라 분기:
  - "fixed":    sliding window (기존 방식)
  - "semantic": 임베딩 유사도 breakpoint 기반 (Phase 2에서 구현)
"""

from typing import Dict, List

from langsmith import traceable

from ..config import EmbeddingCfg, get_stage_config


@traceable(name="ingest.6_chunk", run_type="tool")
def chunk_segments(
    segments: List[Dict],
    cfg: EmbeddingCfg | None = None,
) -> List[Dict]:
    cfg = cfg or get_stage_config().embedding
    if not segments:
        return []

    if cfg.chunking_strategy == "semantic":
        return _chunk_semantic(segments, cfg)
    return _chunk_fixed(segments, cfg)


def _chunk_fixed(segments: List[Dict], cfg: EmbeddingCfg) -> List[Dict]:
    """고정 sliding window 기반 청킹."""
    window_seconds = cfg.chunk_window_seconds
    overlap_seconds = cfg.chunk_overlap_seconds
    step = window_seconds - overlap_seconds
    chunks: List[Dict] = []

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


def _chunk_semantic(segments: List[Dict], cfg: EmbeddingCfg) -> List[Dict]:
    """임베딩 유사도 breakpoint 기반 청킹. Phase 2에서 구현 예정."""
    raise NotImplementedError(
        "semantic chunking은 Phase 2에서 구현 예정. "
        "지금은 CHUNKING_STRATEGY=fixed만 사용 가능합니다."
    )
