"""
diagnostics.py — API 응답에 evals 수준 진단 데이터를 실어주는 유틸리티

evals/_common.py가 CLI 실험용이라면, 이 모듈은 런타임 API 응답용이다.
동일한 관심사(config 스냅샷, 타이밍 계측)를 app 컨텍스트에 맞게 제공한다.
"""

import time
from contextlib import contextmanager
from typing import Any, Dict

from .config import CONFIG
from .prompts import CURRENT_VISION_VERSION, CURRENT_QA_SYSTEM_VERSION

# ── config 스냅샷 ──


def get_config_snapshot() -> Dict[str, Any]:
    """현재 CONFIG 상태를 API 응답에 포함할 dict로 반환한다.

    evals의 get_config_snapshot()과 동일한 키를 유지하여
    evals 결과 JSON과 API 응답 간 비교가 가능하도록 한다.
    """
    is_local = CONFIG.provider == "local"
    return {
        "provider": CONFIG.provider,
        "whisper_model_size": (
            CONFIG.whisper_model_size if is_local else CONFIG.openai_whisper_model
        ),
        "chat_model": (
            CONFIG.ollama_chat_model if is_local else CONFIG.openai_chat_model
        ),
        "vision_model": (
            CONFIG.ollama_vision_model if is_local else CONFIG.openai_vision_model
        ),
        "embed_model": (
            CONFIG.ollama_embed_model if is_local else CONFIG.openai_embedding_model
        ),
        "embedding_dim": CONFIG.embedding_dim,
        "prompt_version": CURRENT_VISION_VERSION,
        "qa_prompt_version": CURRENT_QA_SYSTEM_VERSION,
        "frames_per_minute": CONFIG.frames_per_minute,
        "chunk_window_seconds": CONFIG.chunk_window_seconds,
        "chunk_overlap_seconds": CONFIG.chunk_overlap_seconds,
        "search_threshold": CONFIG.search_threshold,
        "search_top_k": CONFIG.search_top_k,
        "use_rerank": CONFIG.use_rerank,
        "rerank_model": CONFIG.rerank_model,
        "rerank_top_n": CONFIG.rerank_top_n,
        "search_pre_rerank_k": CONFIG.search_pre_rerank_k,
    }


# ── 타이밍 계측 ──


@contextmanager
def timer():
    """경과 시간(ms)을 측정하는 컨텍스트 매니저.

    Usage:
        with timer() as elapsed:
            do_work()
        print(elapsed())  # → 1234 (ms)

    yield 시점부터 측정이 시작되며, 블록 종료 후 elapsed()는 최종 값을 반환한다.
    블록 내에서 elapsed()를 호출하면 그 시점까지의 중간 경과 시간을 얻는다.
    """
    start = time.perf_counter()
    snapshot: Dict[str, int] = {}

    def get_ms() -> int:
        return snapshot.get("ms", round((time.perf_counter() - start) * 1000))

    try:
        yield get_ms
    finally:
        snapshot["ms"] = round((time.perf_counter() - start) * 1000)


class StageTimer:
    """process_media_background 같은 다단계 작업의 구간별 latency를 수집한다.

    Usage:
        st = StageTimer()
        with st.measure("transcribe"):
            segments = transcribe_audio(path)
        with st.measure("vision"):
            frames = analyze_frames(...)
        print(st.result)  # {"transcribe": 3200, "vision": 8100, "total": 11300}
    """

    def __init__(self):
        self._start = time.perf_counter()
        self._stages: Dict[str, int] = {}

    @contextmanager
    def measure(self, stage_name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self._stages[stage_name] = round((time.perf_counter() - t0) * 1000)

    @property
    def result(self) -> Dict[str, int]:
        return {
            **self._stages,
            "total": round((time.perf_counter() - self._start) * 1000),
        }
