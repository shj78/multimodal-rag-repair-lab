"""
qa_pipeline.py — QA 한 건의 오케스트레이션 (route와 util 사이의 pipeline 층)

main.py /qa, evals/_stages.py:run_qa, evaluation_utils.run_full_evaluation에
중복돼 있던 "embedding → retrieve → generate" 흐름을 하나로 모은 shared boundary.
이번 PR에선 main.py만 이 함수를 호출하도록 교체하고, evals 쪽은 별도 PR에서 교체.

LangSmith trace 구조:
    qa.request (root, run_type="chain")
      ├─ query_embedding   (get_text_embedding @traceable)
      ├─ run_retrieve      (chain)
      │   ├─ vector_search       (search_similar_segments @traceable)
      │   └─ candidate_ranking   (_rank_candidates @traceable + mode metadata)
      └─ run_generate      (chain)
          └─ chat_completion     (get_answer_by_chat_model @traceable)

LANGCHAIN_TRACING_V2가 false이거나 키가 없으면 @traceable은 투명 pass-through로
동작하므로 로컬·CI 환경에서도 키 없이 그대로 돌아간다.
"""

from typing import Any, Dict, Optional

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from ..config import PipelineConfig, get_stage_config
from ..diagnostics import timer
from ..embedding import get_text_embedding
from ..qa.chat import get_answer_by_chat_model
from ..qa.retrieval import retrieve_segments


@traceable(name="qa.request", run_type="chain")
def run_qa(
    query: str,
    media_id: str,
    cfg: Optional[PipelineConfig] = None,
) -> Dict[str, Any]:
    """질문 1건을 처리해 답변·근거·구간별 latency·trace_id를 반환한다.

    응답 dict의 latency_ms shape은 기존 /qa 응답과 동일하게
    {embedding, retrieval, generation, total} 4-key를 유지한다.
    """
    cfg = cfg or get_stage_config()
    latency_ms: Dict[str, int] = {}

    with timer() as t_embed:
        query_embedding = get_text_embedding(query, cfg=cfg.embedding)
    latency_ms["embedding"] = t_embed()

    with timer() as t_retrieve:
        all_segments, accepted = run_retrieve(
            query, query_embedding, media_id, cfg
        )
    latency_ms["retrieval"] = t_retrieve()

    with timer() as t_gen:
        answer, context_text = run_generate(query, accepted, cfg)
    latency_ms["generation"] = t_gen()

    latency_ms["total"] = (
        latency_ms["embedding"] + latency_ms["retrieval"] + latency_ms["generation"]
    )

    run = get_current_run_tree()
    trace_id = str(run.id) if run is not None else None

    return {
        "answer": answer,
        "context_text": context_text,
        "all_segments": all_segments,
        "accepted": accepted,
        "latency_ms": latency_ms,
        "trace_id": trace_id,
    }


@traceable(run_type="chain")
def run_retrieve(
    query: str,
    query_embedding,
    media_id: str,
    cfg: PipelineConfig,
):
    """검색 + 선별 단계를 trace의 child run으로 노출한다."""
    return retrieve_segments(query, query_embedding, media_id, cfg=cfg.retrieval)


@traceable(run_type="chain")
def run_generate(
    query: str,
    accepted_segments,
    cfg: PipelineConfig,
):
    """답변 생성 단계를 trace의 child run으로 노출한다."""
    return get_answer_by_chat_model(query, accepted_segments, cfg=cfg.qa)
