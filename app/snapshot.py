"""
snapshot.py — config + prompt 스냅샷 단일 진실 공급원

config-규약 "Snapshot 단일화" 항목 구현.
diagnostics.py(런타임 API 응답용)와 evals/_common.py(CLI 실험용)가
모두 이 모듈을 import한다.

출력 키는 evals/results/ JSON 형식과 동일하게 유지한다.
"""

from typing import Any, Dict

from .config import get_stage_config
from .prompts import (
    CURRENT_QA_SYSTEM_VERSION,
    CURRENT_RERANK_DOC_VERSION,
    CURRENT_VISION_VERSION,
    EVAL_ANSWER_RELEVANCE_PROMPT,
    EVAL_GROUNDEDNESS_PROMPT,
    EVAL_RETRIEVAL_PRECISION_PROMPT,
    EVAL_VISUAL_TEXT_ALIGNMENT_PROMPT,
    QA_SYSTEM_PROMPTS,
    RERANK_DOC_TEMPLATES,
    VISION_PROMPTS,
)


def get_config_snapshot() -> Dict[str, Any]:
    """현재 CONFIG 상태를 실험/API 응답에 포함할 dict로 반환한다.

    Stage Config의 .model_dump()를 활용하여 생성하므로,
    get_stage_config() → override_config() 체인이 올바르게 반영된다.
    """
    cfg = get_stage_config()
    transcription = cfg.transcription
    vision = cfg.vision
    embedding = cfg.embedding
    retrieval = cfg.retrieval
    qa = cfg.qa

    is_local = transcription.provider == "local"

    return {
        "provider": transcription.provider,
        "vision_provider": vision.provider,
        "chat_provider": qa.provider,
        "judge_provider": cfg.judge.provider,
        "whisper_model_size": (
            transcription.whisper_model_size
            if is_local
            else transcription.openai_whisper_model
        ),
        "openai_whisper_model": transcription.openai_whisper_model,
        "chat_model": qa.ollama_chat_model if is_local else qa.openai_chat_model,
        "vision_model": (
            vision.ollama_vision_model if is_local else vision.openai_vision_model
        ),
        "embed_model": (
            embedding.ollama_embed_model
            if is_local
            else embedding.openai_embedding_model
        ),
        "embedding_dim": embedding.embedding_dim,
        "prompt_version": CURRENT_VISION_VERSION,
        "qa_prompt_version": CURRENT_QA_SYSTEM_VERSION,
        "frames_per_minute": vision.frames_per_minute,
        "chunk_window_seconds": embedding.chunk_window_seconds,
        "chunk_overlap_seconds": embedding.chunk_overlap_seconds,
        "search_threshold": retrieval.search_threshold,
        "search_top_k": retrieval.search_top_k,
        "use_rerank": retrieval.use_rerank,
        "rerank_model": retrieval.rerank_model,
        "rerank_top_n": retrieval.rerank_top_n,
        "search_pre_rerank_k": retrieval.search_pre_rerank_k,
    }


def get_prompt_snapshot() -> Dict[str, Any]:
    """현재 프롬프트 버전 + 전문을 기록할 dict로 반환한다.

    config-규약 "누락 추가" 항목: rerank doc prompt, EVAL_* 4종 포함.
    """
    return {
        "vision": {
            "version": CURRENT_VISION_VERSION,
            "text": VISION_PROMPTS[CURRENT_VISION_VERSION],
        },
        "qa_system": {
            "version": CURRENT_QA_SYSTEM_VERSION,
            "text": QA_SYSTEM_PROMPTS[CURRENT_QA_SYSTEM_VERSION],
        },
        "rerank_doc": {
            "version": CURRENT_RERANK_DOC_VERSION,
            "text": RERANK_DOC_TEMPLATES[CURRENT_RERANK_DOC_VERSION],
        },
        "eval_answer_relevance": EVAL_ANSWER_RELEVANCE_PROMPT,
        "eval_groundedness": EVAL_GROUNDEDNESS_PROMPT,
        "eval_retrieval_precision": EVAL_RETRIEVAL_PRECISION_PROMPT,
        "eval_visual_text_alignment": EVAL_VISUAL_TEXT_ALIGNMENT_PROMPT,
    }
