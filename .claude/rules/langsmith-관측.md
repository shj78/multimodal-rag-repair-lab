---
description: LangSmith 관측 규칙. @traceable 이름, run_type, stage grouping, helper 경계.
paths:
  - "app/**"
---

# LangSmith 관측 규칙

> app/ 코드에 LangSmith `@traceable`을 부착·수정할 때 적용되는 규칙.
> 루트 CLAUDE.md의 "변경에는 맥락이 따라다닌다", "기록 = 실행" 원칙을 관측 도메인에서 구현한 것.
---

## 1. 개념 (최소 3개)

LangSmith를 쓰면서 헷갈릴 때 이 세 가지만 기억한다.

| 개념 | 정의 | 예시 |
| --- | --- | --- |
| **trace** | 요청 1건의 기록 (HTTP 요청 1 = trace 1) | `/qa` 한 번 호출 |
| **run** | trace 내부 함수 호출 하나 | `qa.1_embed_query`, `qa.2_vector_search` |
| **run_type** | run의 분류 라벨 | `chain` / `llm` / `retriever` / `embedding` / `tool` |

- 루트 run의 이름이 LangSmith UI에서 trace 대표 이름으로 표시된다 (trace 자체는 이름 없음)
- run은 `@traceable` 데코레이터로 생성된다
- `LANGCHAIN_TRACING_V2=false`이거나 키가 없으면 `@traceable`은 투명 pass-through로 동작 → 코드는 관측 의존 없이 돌아간다

---

## 2. 이름 규칙

```
루트:   {domain}.request                  # 예: qa.request, ingest.request
묶음:   {domain}.{이름}                    # 예: qa.retrieve
말단:   {domain}.{번호}_{동작}             # 예: qa.1_embed_query
계층:   {domain}.{부모번호}.{자식번호}_...  # 예: qa.3.1_rerank
```

**세부 규칙**:

- `domain`은 app 도메인 이름 (현재 `qa`, `ingest`). 도메인 정의는 `app-구조.md` §2 참조
- 번호는 **말단(leaf) run에만** 붙인다. 루트·묶음엔 번호 없음
- 번호는 **도메인 내 실행 순서의 현 스냅샷**. 파이프라인 재구성 시 재매김 허용
- 말단 중 다른 말단을 자식으로 가지면 `3.1`처럼 계층 번호 (현재는 `qa.3.1_rerank` 한 사례)
- 이름은 **함수명이 아니라 도메인 언어** — 함수명 리팩토링 시 UI 대시보드·필터가 깨지지 않게

**왜**: `{domain}.` 접두사는 LangSmith Runs 리스트에서 `Name: starts_with "qa."` 한 줄 필터로 도메인별 분리 가능. 번호는 알파벳 정렬만으로 실행 순서가 보여서 파이프라인 지도 역할.

**코드 이름과 trace 이름은 역할이 다르다**:

- `@traceable(name=...)`의 `name`이 **관측 계약**이다. LangSmith 필터·대시보드·운영 메모는 이 이름을 기준으로 본다.
- Python 함수명은 코드 내부 안정성을 우선한다. observability만의 이유로 기존 leaf util 이름을 자주 바꾸지 않는다.
- leaf util은 trace 이름과 1:1로 맞출 필요가 없다. 예: `get_answer_by_chat_model` ↔ `qa.4_chat_completion`

**pipeline 내부 private helper의 trace 이름**: grouping 전용 helper(`_trace_*`, `app-구조.md` §3 참조)는 LangSmith 이름을 도메인 언어로 둔다. 예: `_trace_vision` ↔ `ingest.vision`.

---

## 3. run_type 지침

| run_type | 언제 | 특별 처리 |
| --- | --- | --- |
| `chain` | **자식 run을 품는 묶음** | UI에서 부모 역할 |
| `llm` | **`chat.completions` 호출** (용도 무관) | 토큰·비용 자동 집계 (OpenAI SDK 어댑터 경로에서만) |
| `retriever` | 검색·재정렬 (vector search, rerank) | RAG 검색 전용 UI |
| `embedding` | 텍스트 → 벡터 변환 | 벡터 전용 UI |
| `tool` | 그 외 말단 전부 | 범용 (기본 안전값) |

**핵심 구분은 `chain` vs 나머지**: chain만 "묶음", 나머지는 전부 "말단". 함수가 다른 `@traceable`을 호출하면 chain, 혼자 일하면 말단.

**`llm`의 엄밀한 정의** (현업 관행):

- `llm`은 **"prompt → text completion"** 호출 전용 (chat completions / text completions API)
- Whisper(`audio.transcriptions`)는 **llm 아님** → `tool`
- Embeddings API는 `embedding`이지 `llm`이 아님
- 비전 모델(GPT-4V)은 `chat.completions`를 사용하므로 **`llm`**
- vision-guided correction도 `chat.completions` 사용이므로 **`llm`**

**왜**: `llm` 태그가 비용 집계의 트리거라서 오분류하면 집계 신뢰성이 오염된다. Ollama 로컬 모드에선 자동 집계가 안 되지만, run_type은 의미상 맞게 둬야 OpenAI 전환 시 자동 작동.

---

## 4. 부착 원칙

층 구분은 `app-구조.md` §1~2를 따른다. 각 층의 관측 부착 여부:

| 층 | 부착 여부 |
| --- | --- |
| route (`main.py`) | ✗ — HTTP 입출력만, trace 시작점 |
| **pipeline** (`pipelines/*.py`) | **항상** — 루트 + 주요 묶음 |
| **도메인 util** (`ingest/*.py`, `qa/*.py`) | **관찰 가치 있을 때** (API 호출, 지연 큰 단계, 프롬프트 관련) |
| **공유 도메인** (`embedding.py`) | **부착** — 호출 맥락별로 분리 (§5 참조) |
| 인프라 (`config.py`, `prompts.py`, `diagnostics.py`, `snapshot.py`) | ✗ |
| 인프라 예외 (`supabase_utils.py:search_similar_segments`) | ✓ — 관측 가치 큰 외부 호출 |
| 메타 (`evaluation_utils.py`) | ✗ — `run_qa`를 재호출하는 방향으로 장기 일원화 예정 |

**1:1 래퍼는 trace tree에도 잡음**: 구조 규칙상 1:1 래퍼는 금지되지만(`app-구조.md` §6), 관측 측면에서도 자식이 1개인 `chain` 노드는 trace tree에 의미 없는 층을 추가한다. chain은 **자식 2개 이상**일 때만 관측 가치가 있다.

**예외 — major grouping helper**: ingest처럼 leaf run이 루프 때문에 길게 펼쳐져 trace 가독성이 떨어질 때는 pipeline 내부 `_trace_*` helper로 묶음을 둔다 (구조 규칙 `app-구조.md` §3 참조). LangSmith 이름은 `ingest.vision`처럼 도메인 언어로 둔다.

---

## 5. 동명 함수 처리

같은 함수가 여러 맥락에서 쓰이면 **얇은 래퍼로 이름을 분리**한다. 단일 `@traceable(name=...)`은 이름을 함수에 박아서 호출 맥락별 구분이 안 된다.

**현재 적용 사례**: `embedding.py`

```python
def _embed_text(text, cfg):   # un-decorated 내부 공통 로직
    ...

@traceable(name="qa.1_embed_query", run_type="embedding")
def embed_query(text, cfg):   # qa 맥락
    return _embed_text(text, cfg)

@traceable(name="ingest.8_embed_chunk", run_type="embedding")
def embed_chunk(text, cfg):   # ingest 맥락
    return _embed_text(text, cfg)
```

**왜 얇은 래퍼**: run 이름을 함수에 박으면 호출처마다 다른 이름을 줄 수 없음. `@traceable`을 호출부에서 동적으로 감싸는 방식은 호출부가 지저분. 래퍼 2개로 나눠두면 이름·역할·run_type이 명확히 분리됨.

---

## 6. 현재 Tree 스냅샷

delta-03-lang-v2 기준. 향후 파이프라인 변경 시 이 섹션 갱신.

### QA (hyde + hybrid + LLM rerank 모드, 기본값)

```
qa.request                 [chain]
  qa.0_hyde                [llm]          쿼리 → 가상 답변 (use_hyde=True 시)
  qa.1_embed_query         [embedding]    HyDE 활성 시 가상 답변을 임베딩
  qa.retrieve              [chain]
    qa.2_search            [chain]        hybrid fusion 묶음
      qa.2.1_vector_search [retriever]    후보 rerank_pool_size개 반환
      qa.2.2_bm25_search   [retriever]    원 쿼리 기준 BM25 상위 hybrid_bm25_top_k개
      qa.2.3_rrf_fuse      [tool]         RRF로 두 ranking 병합
    qa.3_rank_candidates   [chain]        metadata: mode=rerank, rerank_provider=llm
      qa.3.1_llm_rerank    [llm]          listwise LLM rerank (rerank_provider=llm 시)
  qa.4_chat_completion     [llm]          토큰 자동 집계 (OpenAI 시)
```

### QA (rerank_provider=cohere 경로)

```
qa.request                 [chain]
  qa.0_hyde                [llm]          (use_hyde=True 시)
  qa.1_embed_query         [embedding]
  qa.retrieve              [chain]
    qa.2_search            [chain]
      qa.2.1_vector_search [retriever]
      qa.2.2_bm25_search   [retriever]
      qa.2.3_rrf_fuse      [tool]
    qa.3_rank_candidates   [chain]        metadata: mode=rerank, rerank_provider=cohere
      qa.3.1_cohere_rerank [retriever]    Cohere cross-encoder rerank
  qa.4_chat_completion     [llm]
```

**쿼리 흐름 주의:** `qa.0_hyde`가 만든 가상 답변은 `qa.1_embed_query`에만 쓰인다.
BM25(`qa.2.2`)와 rerank(`qa.3.1_*`)는 **원 쿼리**를 그대로 쓴다 — 희귀 토큰
매칭과 rerank 판단이 HyDE의 가상 어휘로 희석되지 않게 하기 위함.

**Rerank provider 선택:** `RERANK_PROVIDER` env var 또는 `rerank_provider` config 필드.
기본 `"llm"`. Cohere cross-encoder는 영상 내부 alias("꽁꽁이 ↔ 고양이") 해결에
약하므로 LLM rerank를 기본값으로 채택.

### QA (hybrid + threshold 모드, use_hyde=False)

```
qa.request                 [chain]
  qa.1_embed_query         [embedding]
  qa.retrieve              [chain]
    qa.2_search            [chain]
      qa.2.1_vector_search [retriever]    후보 top_k 반환
      qa.2.2_bm25_search   [retriever]    BM25 상위 hybrid_bm25_top_k개
      qa.2.3_rrf_fuse      [tool]
    qa.3_rank_candidates   [chain]        metadata: mode=threshold (자식 없음)
  qa.4_chat_completion     [llm]
```

### QA (use_hybrid=False, use_hyde=False, rollback 경로)

```
qa.request                 [chain]
  qa.1_embed_query         [embedding]
  qa.retrieve              [chain]
    qa.2_search            [chain]        자식 1개인 얕은 chain (hybrid 끈 상태)
      qa.2.1_vector_search [retriever]
    qa.3_rank_candidates   [chain]
      qa.3.1_rerank        [retriever]    (use_rerank=True 시)
  qa.4_chat_completion     [llm]
```

### Ingest

```
ingest.request             [chain]
  ingest.transcribe        [chain]
    ingest.1_audio_extract [tool]         ffmpeg
    ingest.2_transcribe    [tool]         Whisper (chat 아님)
  ingest.vision            [chain]
    ingest.3_extract_frames [tool]        ffmpeg
    ingest.4_analyze_frame [llm]   × N    GPT-4V chat.completions
  ingest.5_correct         [llm]          enabled + frame 존재 시에만
  ingest.embed             [chain]
    ingest.6_chunk         [tool]         순수 Python
    ingest.7_multimodal    [tool]  × N    순수 Python
    ingest.8_embed_chunk   [embedding] × N
```

---

## 7. 냄새 신호

- `run_generate` 같은 1:1 래퍼가 발견된다 → §4에 따라 제거 검토
- 같은 함수가 두 trace에서 이름이 겹친다 → §5 얇은 래퍼로 분리
- Cohere/OpenAI 외부 호출이 `@traceable` 없이 숨어 있다 → §4 관찰 가치 검토
- `llm`이 아닌 run에 `chat.completions`가 들어가 있다 → run_type 오분류, §3 재확인
- 루트 run 없이 말단만 찍힌 고아 run이 보인다 → 호출자에 부모 `@traceable` 없음 (§8 참조)

---

## 8. 미해결 이슈

### evals 호출 경로 고아 run

`evals/_stages.py`는 현재 `pipelines.run_ingest` / `pipelines.run_qa`를 호출하지 않고 도메인 util을 **직접 호출**한다. 이 util들에 `@traceable`이 달려 있으므로, evals 실행 시 각 호출이 **부모 없는 루트 trace**로 찍힌다.

- 증상: LangSmith에 `ingest.6_chunk`, `ingest.7_multimodal`, `qa.2_vector_search` 등이 루트 레벨에서 대량으로 생성
- 원인: evals가 파이프라인 오케스트레이션을 자체 재현 (`_stages.py`의 embed/qa 단계가 util 순차 호출)
- 임시 대응: Runs 리스트 필터로 `Name contains ".request"` 걸어 고아 run 숨김
- 근본 해결: 별도 PR에서 `evals/_stages.py`와 `evaluation_utils.run_full_evaluation`이 `run_qa` / `run_ingest`를 호출하도록 교체

### Ollama 로컬 모드의 `llm` 집계

`llm` run_type은 OpenAI SDK 어댑터 경로에서만 토큰·비용이 자동 집계된다. `analyze_frame_with_vision_model`·`correct_transcription_with_vision`이 Ollama 분기일 때(`requests.post` 직접 호출)는 집계 안 됨. run_type은 의미상 유지하고, 필요 시 수동 metadata로 보완.

---

## 9. 변경 원칙

- 이 문서는 **운영 규칙**이지 생각의 기록이 아니다. 논의·대안·기각 근거는 여기 담지 않는다.
- 규칙을 추가·변경할 때는 **왜 추가하는지 한 줄**과 **적용 시 체크할 것**을 함께 적는다.
- 현업 관행과 어긋나는 예외를 둘 때는 "왜 우리는 다르게 가는지" 근거를 명시한다.
