---
description: Config 리팩토링 규약. Stage Config 패턴, 호출 규약, Override 레이어.
paths:
  - "app/**"
  - "evals/_stages.py"
---

# Config 규약

> app/ 코드를 수정할 때 적용되는 config 관련 규칙.
> 루트 CLAUDE.md의 "기록 = 실행" 원칙을 코드 레벨에서 구현한 것.

---

## 호출 규약

import-time에 CONFIG default를 평가하는 패턴을 금지한다.

```python
# 금지 — import 시점에 값 고정, evals override 불가
def segment_transcript(segments, window_seconds=CONFIG.chunk_window_seconds):

# 허용 — 호출 시점에 lazy lookup
def segment_transcript(segments, cfg: EmbeddingCfg | None = None):
    cfg = cfg or get_stage_config().embedding
```

**왜**: Python default는 정의 시점에 평가된다. CONFIG를 default에 넣으면 evals에서 override해도 원래 값이 사용되는 버그가 생긴다. Sprint 3에서 media_utils, retrieval_utils, supabase_utils에 이 패턴이 있었다.

수정 대상:
- `media_utils.py` — `segment_transcript()`, `get_text_embedding()`
- `retrieval_utils.py` — `rerank_segments()`
- `supabase_utils.py` — `search_similar_segments()`
- `evals/_stages.py` — live CONFIG 직접 참조 제거

---

## Stage Config

파이프라인 단계별 설정을 Pydantic BaseModel로 분리한다. 단위는 "knob이 함께 움직이는 범위" = stage.

| Stage | Config | 파일 | 비고 |
| --- | --- | --- | --- |
| transcribe | TranscriptionCfg | transcription_utils.py | |
| vision | VisionCfg | vision_utils.py | |
| embedding | EmbeddingCfg | media_utils.py | |
| retrieval | RetrievalCfg | retrieval_utils.py | |
| qa | QACfg | chat_utils.py | |
| judge | JudgeCfg | evaluation_utils.py | 1급 시민 — QA와 독립 |

- `.model_dump()` → snapshot 생성 (기록 = 실행 보장)
- `.model_copy(update=...)` → override 시 사용
- `supabase_utils.py`는 embedding + retrieval 두 stage에 걸침 (예외)

**왜 JudgeCfg가 1급 시민인가**: Sprint 3 exp-06에서 "judge 모델과 chat 모델이 같으면 편향"을 발견했다. judge는 다른 stage와 동일 레벨에서 독립적으로 존재해야 한다.

---

## Snapshot 단일화

기존 snapshot 로직이 diagnostics.py와 _common.py에 중복되어 있고, 일부 프롬프트가 누락돼 있었다.

- `app/snapshot.py` 신규 — `get_config_snapshot()` + `get_prompt_snapshot()` 단일 함수
- 두 곳 모두 이 함수를 import (중복 제거)
- 누락 추가: rerank doc prompt, EVAL_*_PROMPT 4종, vision/QA prompt 버전

---

## Override 레이어

AI가 연속 실험 시 config.py를 직접 수정하지 않고 override 블록을 사용한다.

```python
with override_config(vision={"frames_per_minute": 6}):
    run_experiment(...)
# 블록 종료 시 자동 복원
```

두 경로 공존:
- **직접 실험** → config.py 수정 (기존 방식)
- **AI 연속 실험** → override 블록 (config.py 안 건드림, 자동 복원)

**왜 공존인가**: 직접 실험할 때 override 블록은 여러 인자를 다루기 번거롭다. 기존 방식도 유지하되, AI가 5개 후보를 연속으로 돌리는 패턴에서는 override가 config 오염을 방지한다.

---

## Provider 분리

현재 단일 `provider` 필드를 역할별로 분리한다. 개수는 페어 합의 후 결정 (3개 또는 4개).

---

## 임베딩 모델 + 테이블 분리

임베딩 모델별 Supabase 테이블을 분리한다.

```
segments_nomic_768      -- 기존 유지
segments_bge_m3_1024    -- 새로 생성
```

config의 embed 모델에 따라 테이블 + match 함수를 자동 선택한다. 기존 데이터 유지, 비교 실험 가능.

---

## 냄새 신호 (config 특화)

- 함수 시그니처에 `CONFIG.xxx` default가 보인다 → Phase A 미적용
- `.model_dump()` 결과와 실제 전달된 값이 다르다 → 양다리 재발
- fixture의 config fingerprint와 현재 config가 불일치 → config drift
- 같은 실험을 두 번 돌렸는데 config snapshot이 다르다 → 환경 오염
