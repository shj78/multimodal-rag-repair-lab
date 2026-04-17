"""
qa/retrieval.py — 검색 결과 선별 (Rerank / Threshold)

retrieve_segments: 검색 → 선별 → accepted 마킹까지의 공통 흐름.
rerank_segments:   Cohere Rerank 호출 (retrieve_segments 내부에서 사용).
"""

from typing import List, Dict, Any, Tuple

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from ..config import RetrievalCfg, get_stage_config
from ..prompts import format_rerank_document


@traceable(name="qa.3.1_rerank", run_type="retriever")
def rerank_segments(
    query: str,
    segments: List[Dict[str, Any]],
    cfg: RetrievalCfg | None = None,
) -> List[Dict[str, Any]]:
    """
    Cohere Rerank로 segments를 재정렬하여 상위 top_n개를 반환한다.
    COHERE_API_KEY가 없거나 API 호출 실패 시 원본을 그대로 반환 (fallback).

    fallback 경로 진입 시 run.metadata에 `skipped` 키로 사유를 남겨
    LangSmith trace만 보고도 "실제 Cohere 호출이 있었는지"를 판별할 수 있다.
    """
    cfg = cfg or get_stage_config().retrieval
    top_k = cfg.rerank_top_k
    run = get_current_run_tree()

    if not cfg.cohere_api_key:
        print("[rerank] COHERE_API_KEY 없음 — rerank 생략")
        if run is not None:
            run.add_metadata({"skipped": "no_api_key"})
        return segments[:top_k]

    if not segments:
        return segments

    try:
        import cohere

        client = cohere.ClientV2(api_key=cfg.cohere_api_key)

        documents = [format_rerank_document(seg) for seg in segments]

        response = client.rerank(
            model=cfg.rerank_model,
            query=query,
            documents=documents,
            top_n=top_k,
        )

        reranked = []
        for result in response.results:
            seg = segments[result.index].copy()
            seg["rerank_score"] = result.relevance_score
            seg["accepted"] = True
            reranked.append(seg)

        scores = [f"{s['rerank_score']:.3f}" for s in reranked]
        print(f"[rerank] {len(segments)}개 → {len(reranked)}개 선별 (scores: {scores})")
        return reranked

    except Exception as e:
        print(f"[rerank] 실패, fallback 사용 — {e}")
        if run is not None:
            run.add_metadata({"skipped": "api_error", "error": str(e)})
        return segments[:top_k]


@traceable(name="qa.3_rank_candidates", run_type="chain")
def _rank_candidates(
    candidates: List[Dict[str, Any]],
    query: str,
    cfg: RetrievalCfg,
) -> List[Dict[str, Any]]:
    """검색 결과 후보를 rerank 또는 threshold로 선별한다.

    cfg.use_rerank로 분기한다. 이전엔 rerank는 retrieval_utils, threshold는
    supabase_utils에 흩어져 있었지만 "선별"이라는 동일 관심사를 한 함수로 통합.

    LangSmith trace에는 mode metadata로 분기를 노출 — UI에서 rerank/threshold
    경로를 한 run 이름(candidate_ranking) 안에서 비교할 수 있도록.
    """
    run = get_current_run_tree()
    if cfg.use_rerank:
        if run is not None:
            run.add_metadata(
                {
                    "mode": "rerank",
                    "rerank_model": cfg.rerank_model,
                    "rerank_top_k": cfg.rerank_top_k,
                }
            )
        return rerank_segments(query, candidates, cfg=cfg)

    if run is not None:
        run.add_metadata(
            {"mode": "threshold", "threshold": cfg.search_threshold}
        )
    return [c for c in candidates if c.get("similarity", 0) >= cfg.search_threshold]


def retrieve_segments(
    query: str,
    query_embedding: List[float],
    media_id: str,
    cfg: RetrievalCfg | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    검색 → 선별(rerank/threshold) → accepted 마킹까지 한번에 처리.

    Returns:
        (all_segments, accepted_segments)
        - all_segments: 전체 후보 (accepted 필드 마킹됨)
        - accepted_segments: 최종 선별된 세그먼트
    """
    cfg = cfg or get_stage_config().retrieval
    from ..supabase_utils import search_similar_segments

    # rerank 모드는 후보 풀을 rerank_pool_size까지 넓혀서 가져온다.
    search_cfg = cfg
    if cfg.use_rerank:
        search_cfg = cfg.model_copy(
            update={"top_k": cfg.rerank_pool_size}
        )

    # threshold 적용은 _rank_candidates가 담당하므로 search 단계는 항상 skip.
    all_segments = search_similar_segments(
        query_embedding,
        media_id,
        cfg=search_cfg,
        skip_threshold=True,
    )

    accepted_segments = _rank_candidates(all_segments, query, cfg)

    # accepted 마킹 (응답/결과 JSON의 sources에서 선별 여부 표시)
    # rerank은 .copy()된 객체를 반환하므로 id()가 아닌 chunk_index로 비교
    accepted_indices = {s.get("chunk_index") for s in accepted_segments}
    for seg in all_segments:
        seg["accepted"] = seg.get("chunk_index") in accepted_indices

    return all_segments, accepted_segments
