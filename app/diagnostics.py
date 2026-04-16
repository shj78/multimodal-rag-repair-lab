"""
diagnostics.py — API 응답에 evals 수준 진단 데이터를 실어주는 유틸리티

evals/_common.py가 CLI 실험용이라면, 이 모듈은 런타임 API 응답용이다.
동일한 관심사(config 스냅샷, 타이밍 계측)를 app 컨텍스트에 맞게 제공한다.
"""

import time
from contextlib import contextmanager
from typing import Any, Dict

from .snapshot import get_config_snapshot  # noqa: F401 — re-export for callers

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

    def record(self, stage_name: str, duration_ms: int) -> None:
        self._stages[stage_name] = duration_ms

    @property
    def result(self) -> Dict[str, int]:
        return {
            **self._stages,
            "total": round((time.perf_counter() - self._start) * 1000),
        }
