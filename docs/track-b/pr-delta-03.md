# PR: Delta-03 — 파이프라인 고도화 + Vision-guided 전사 교정

## 변경 요약

| 분류 | 내용 |
|------|------|
| refactor | Stage Config 모델 도입 + 호출 규약 수정 |
| refactor | Provider 4개 분리 + Snapshot/Override 구현 |
| feat | Vision-guided 전사 교정 기능 추가 |
| feat | 미디어 파일 서빙 엔드포인트 |
| feat(evals) | EVAL 프롬프트 버전화 + 교정 파이프라인 연동 |
| docs | 하네스 설계 (CLAUDE.md, settings.json) |
| data | 전사 교정 OFF vs ON 실험 결과 |
| feat | Vision 프롬프트 v5.4 — `print()` 음차 교정 추가 |
| refactor | app/ 3층 구조 개편 (ingest/ · qa/ · pipelines/) |
| refactor | LangSmith `@traceable` 이름·run_type 정비 |
| fix | asyncio.to_thread 이벤트 루프 해방 + Vision 프레임 병렬화 |
| fix | 파일 업로드 메모리 적재 → 1MB 청크 스트리밍 |
| refactor | RetrievalCfg 필드 rename + chunk_segments 이름 정리 |
| feat(retrieval) | BM25 + RRF Hybrid Search 추가 |
| feat(retrieval) | HyDE — 가상 답변 임베딩으로 recall 개선 |
| feat(retrieval) | LLM rerank + rerank_provider 스위치 |
| data | Delta-05 Vision 모델 업그레이드 (gpt-5.4) 실험 |
| feat | QA 프롬프트 v3-cot — CoT 3단계 열거 구조 추가 |
| feat | Vision 프롬프트 v6-scene — 비코드 영상용 장면 서술 구조 |
| feat(ingest) | 프레임 추출 동적 간격 + temperature=0 + 타임스탬프 포함 저장 |
| docs | Retrieval 실험 E·F 기록 (threshold 모드, Cohere+kiwipiepy) |
| fix(observability) | LangSmith orphan root — ThreadPoolExecutor 부모 run 명시 전달 |
| feat(observability) | LangSmith run·Supabase metadata에 config snapshot 부착 |
| chore(harness) | evals/ 동결 반영 — 규칙·스캐너에서 참조 제거 |
| feat(schema) | media_segments.speaker_id 컬럼 + 화자 메타 헬퍼 |
| feat(prompts) | HyDE/LLM-rerank v2-speaker 프롬프트 + uses_speakers 헬퍼 |
| feat(qa) | speaker 메타를 retrieve/rerank/context_text에 통합 |

---

## 1. Stage Config 모델 도입

### 설명

`app/config.py`에 파이프라인 단계별 Pydantic `BaseModel` 7종을 추가했다. 기존 flat `CONFIG` 객체에서 직접 속성을 참조하던 코드를 Stage Cfg 주입 패턴으로 전환했다.

- `TranscriptionCfg` / `VisionCfg` / `EmbeddingCfg` / `CorrectionCfg` / `RetrievalCfg` / `QACfg` / `JudgeCfg`
- `get_stage_config()` — 호출 시점의 `CONFIG` 기준으로 `PipelineConfig`를 빌드해 반환

함수 시그니처에 `CONFIG.xxx`를 default로 넣는 패턴을 금지했다. Python default는 정의 시점에 평가되므로 `override_config()` 블록 안에서도 원래 값이 사용되는 버그가 생긴다.

### 예시

```python
# 이전 — import-time에 값 고정
def transcribe_audio(audio_path, model_size=CONFIG.whisper_model_size):
    ...

# 이후 — 호출 시점 lazy lookup
def transcribe_audio(audio_path: str, cfg: TranscriptionCfg | None = None):
    cfg = cfg or get_stage_config().transcription
    ...
```

---

## 2. Provider 4개 분리

### 설명

단일 `CONFIG.provider`가 파이프라인 전체 provider를 결정하던 구조에서, 단계별로 독립시켰다.

| stage | 환경변수 | 기본값 |
|-------|----------|--------|
| 전사 | `TRANSCRIBE_PROVIDER` | `local` |
| 비전 | `VISION_PROVIDER` | `local` |
| 임베딩 | `EMBEDDING_PROVIDER` | `local` |
| 교정 | `CORRECTION_PROVIDER` | `openai` |
| QA | `CHAT_PROVIDER` | `local` |
| Judge | `JUDGE_PROVIDER` | `local` |

`embedding_dim`은 `EMBEDDING_DIM` env var 또는 활성 모델명에서 자동 결정된다. provider가 아닌 모델명 기준.

```python
_EMBED_DIMS = {
    "nomic-embed-text": 768,
    "bge-m3": 1024,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}
```

### 예시

```ini
# .env — 혼합 구성 예시
TRANSCRIBE_PROVIDER=openai
VISION_PROVIDER=openai
EMBEDDING_PROVIDER=local   # bge-m3 (1024d)
CHAT_PROVIDER=openai
JUDGE_PROVIDER=openai
```

---

## 3. Snapshot/Override 구현

### 설명

**`override_config()`** — `with` 블록 안에서만 CONFIG 값을 교체하고, 블록 종료 시 자동 복원한다. 연속 실험에서 config.py를 직접 수정하지 않고 파라미터를 변경할 수 있다.

**`app/snapshot.py`** — `diagnostics.py`(런타임)와 `evals/_common.py`(CLI) 양쪽에서 import하는 단일 진실 공급원. `get_config_snapshot()` / `get_prompt_snapshot()`을 제공한다.

### 예시

```python
from app.config import override_config

with override_config(vision={"frames_per_minute": 6}):
    run_experiment(...)   # frames_per_minute=6 로 실행
# 블록 종료 시 자동 복원

# 실험 결과 JSON에 포함
from app.snapshot import get_config_snapshot, get_prompt_snapshot

result = {
    "config": get_config_snapshot(),
    "prompts": get_prompt_snapshot(),
    "metrics": {...},
}
```

---

## 4. Vision-guided 전사 교정

### 설명

Whisper 전사 결과의 코드 용어 오류를 Vision 프레임 분석 결과를 근거로 교정하는 단계를 파이프라인에 추가했다.

**흐름**: Vision 프레임 분석 → **전사 교정 (3.5단계)** → 청킹 → 임베딩

`app/correction_utils.py`가 핵심 로직을 담당한다.

- `correct_transcription_with_vision(segments, frame_analyses)` — 타임스탬프가 겹치는 프레임의 vision 설명을 참고해 LLM이 코드 용어를 교정
- `_find_overlapping_frame()` — 세그먼트 `[start, end]`에 타임스탬프가 속하는 프레임 탐색
- 교정 실패 시 경고 로그 후 원문 유지 (파이프라인 중단 없음)

`USE_CORRECTION=false`가 기본값으로, 기존 파이프라인에 영향을 주지 않는다.


교졍된 전사는 media_files 테이블 내 file_transcript 컬럼에 저장한다.
```sql
ALTER TABLE media_files
    ADD COLUMN file_transcript TEXT;
```

### 예시

```python
# segments: Whisper 결과
segments = [
    {"start": 70.0, "end": 90.0, "text": "토탈 변수를 제로로 초기화하고 폴루프로 인트 변환 후 더합니다"},
]

# frame_analyses: Vision v5-code 분석 결과
frame_analyses = [
    {"timestamp": 75.0, "description": "[코드]\ntotal = 0\nfor score in score_list:\n    total += int(score)"},
]

corrected = correct_transcription_with_vision(segments, frame_analyses)
# [{"start": 70.0, "end": 90.0, "text": "total 변수를 0으로 초기화하고 for 루프로 int() 변환 후 더합니다"}]
```

```ini
# .env
USE_CORRECTION=true
CORRECTION_PROVIDER=openai
```

---

## 5. EVAL 프롬프트 버전화

### 설명

평가 프롬프트를 버전별 dict로 관리하고 getter로 접근하도록 통일했다. Vision 프롬프트도 동일 패턴으로 v5-code를 추가했다.

- `EVAL_*_PROMPTS: dict[str, str]` — `{"v1": "...", "v2": "..."}`
- `CURRENT_EVAL_*_VERSION` — 현재 기본 버전 상수
- `get_eval_*_prompt(version=None)` — version 미지정 시 CURRENT 버전 반환
- 실험 결과 JSON의 `prompts` 키에 버전 + 전문이 자동 기록됨

Vision 프롬프트 v5-code는 `[코드]`, `[실행결과]`, `[화면텍스트]`, `[키워드]` 구조화 태그를 사용해 코드 추출 정확도를 높였다.

### 예시

```python
from app.prompts import get_eval_groundedness_prompt, CURRENT_EVAL_GROUNDEDNESS_VERSION

# 현재 버전 사용
prompt = get_eval_groundedness_prompt()

# 버전 명시 비교 실험
for version in ["v1", "v2"]:
    prompt = get_eval_groundedness_prompt(version=version)
    score = run_eval(prompt, ...)
```

---

## 6. 미디어 파일 서빙

### 설명

업로드한 영상을 브라우저에서 직접 재생할 수 있도록 파일 서빙 엔드포인트를 추가했다.

- `supabase_utils.save_media_file()` — `file_path` 파라미터 추가
- `GET /media/{media_id}/file` — DB에서 `file_path` 조회 후 `FileResponse` 반환

```sql
ALTER TABLE media_files
    ADD COLUMN file_path TEXT;
```

### 예시

```python
# GET /media/{media_id}/file
@app.get("/media/{media_id}/file")
async def serve_media_file(media_id: str):
    media = get_media_by_id(media_id)
    return FileResponse(media["file_path"])
```

---

## 7. 하네스 설계

### 설명

Claude Code가 이 레포에서 작동하는 방식을 정의하는 규칙·훅 체계를 구축했다.

- **`CLAUDE.md`** — CONFIG 호출 규약, Snapshot 정합성, 프롬프트 버전 관리, 커밋 규칙 정의
- **`.claude/settings.json`** — `--no-verify` 커밋 차단, `fixtures/` 수동 편집 차단 훅
- **`.claude/rules/`** — config-규약, 실험-프로토콜, code-style 도메인별 분리

---

## 실험 결과 요약

**dataset**: Python 점수 계산 강의, 3분 13초
**고정 조건**: openai whisper-1 / gpt-4o-mini vision **v5.4** / bge-m3 embed / rerank ON
**질문 5개**: T1 비전(내장함수 나열) / T2 비전(total 초기값) / T3 비전(입력 숫자) / T4 단순사실(구분자) / T5 비전(평균 코드)

---

### 전체 실험 비교

총 3라운드, 6개 실험 조건.

| 실험 | correction | correction prompt | whisper prompt | AR | GR | RP |
|------|:----------:|:----------------:|:--------------:|:---:|:---:|:---:|
| 01-A. correction OFF | ✗ | — | ✗ | **0.94** | 0.82 | 0.40 |
| 01-B. correction ON (compare) | ✓ | v1 | ✗ | 0.86 | 0.72 | 0.53 |
| 02-C. correction v1 fresh | ✓ | v1 | ✗ | 0.88 | 0.80 | 0.53 |
| 02-D. correction v2 fresh | ✓ | v2 | ✗ | 0.88 | 0.82 | 0.40 |
| 03-E. whisper v1 + correction v1 | ✓ | v1 | v1 | 0.88 | 0.82 | 0.27 |
| **03-F. whisper v1 + correction v2** | ✓ | v2 | v1 | 0.88 | **0.94** | **0.53** |

> **최종 최고 조합: 03-F** — GR 0.94, RP 0.53

---

### 라운드별 핵심 발견

#### 01 — correction OFF vs ON (`experiments/01-vision-guided-correction/`)

correction 첫 투입(v1, compare 모드) 결과, RP +0.13 개선됐으나 AR과 GR이 모두 하락했다.

| 메트릭 | OFF | ON (v1) | 변화 |
|--------|:---:|:-------:|:----:|
| Answer Relevance | 0.94 | 0.86 | -0.08 |
| Groundedness | 0.82 | 0.72 | **-0.10** |
| Retrieval Precision | 0.40 | 0.53 | **+0.13** |

- T2 (total 초기값) — 전사에 `total = 0` 코드 블록이 삽입되어 RP 0.00 → 0.67 개선
- T1, T3, T4 — 실행 화면 문자열이 전사에 삽입되는 **과교정** 패턴 발생
- compare 모드(기존 전사 fixture 재사용) 특성상 교정만 격리 측정

#### 02 — correction prompt v1 vs v2 (`experiments/02-vision-guided-correction-v2/`)

v2 프롬프트는 과교정을 막기 위해 "전사 순서·구조 변경 금지", "코드 실행 출력 삽입 금지" 제약을 추가했다.

| 메트릭 | correction v1 (fresh) | correction v2 (fresh) | 변화 |
|--------|:---------------------:|:---------------------:|:----:|
| Answer Relevance | 0.88 | 0.88 | — |
| Groundedness | 0.80 | 0.82 | +0.02 |
| Retrieval Precision | 0.53 | 0.40 | -0.13 |

- v2로 과교정 억제에는 성공했으나 RP가 v1 수준으로 돌아감
- v1에서 발생하던 **guard reject 5건** (교정 결과 원문 1.3배 초과 → 원문 유지) → v2에서 **0건**으로 해소
- T5 (평균 코드) — v1에서 GR 0.4 발생(코드 블록 과삽입), v2에서 1.0으로 정상화

#### 03 — Whisper prompt + correction 조합 (`experiments/03-whisper-prompt-correction-v2/`)

Q1 핵심 문제(화자가 "프린트"로 발화 → `print()` context 미포함)를 해결하기 위해 Whisper `prompt` 파라미터로 Python 어휘 힌트를 주입했다.

| 메트릭 | whisper v1 + correction v1 | **whisper v1 + correction v2** |
|--------|:--------------------------:|:------------------------------:|
| Answer Relevance | 0.88 | 0.88 |
| Groundedness | 0.82 | **0.94** |
| Retrieval Precision | 0.27 | **0.53** |

- **Whisper prompt 효과 없음**: 화자가 명확하게 한국어 음차 "프린트"로 발화 → Whisper가 정확하게 전사. `prompt` 파라미터는 발음이 모호한 단어에만 유효하며 명확한 한국어 발화는 override하지 못함
- whisper v1 + correction **v1** 조합은 guard reject가 재발해 RP 0.27로 최저 기록
- whisper v1 + correction **v2** 조합이 전체 실험 중 GR/RP 모두 최고

---

### 질문별 최고/최저 메트릭

| 질문 | 최고 AR | 최고 GR | 최고 RP | 특이사항 |
|------|:-------:|:-------:|:-------:|---------|
| T1 (내장함수 나열) | 1.0 (01-A) | 1.0 (01-A, 03-F) | 0.0 (전 실험) | correction OFF에서만 4개 함수 / RP는 전 실험 0.0 |
| T2 (total 초기값) | 1.0 | 1.0 | 0.67 (01-B) | RP 0.0이 다수 — rerank score 낮음 |
| T3 (입력 숫자) | 0.7 | 1.0 (03-F) | 1.0 (01-A, 02-C, 03-F) | GR이 실험별 편차 큼 (0.3~1.0) / 정답값이 브라우저 다이얼로그 안에만 등장 — Vision 미추출 미해결 |
| T4 (구분자) | 1.0 | 1.0 | 1.0 (02-D, 03-F) | 03-F에서 AR/GR/RP 모두 1.0 |
| T5 (평균 코드) | 1.0 | 1.0 | 1.0 (02-C) | correction v1 fresh에서 RP 최고 |

---

### 미해결 과제 (전사 교정 실험 기준)

1. ~~**`print()` context 미포함** (Critical) — 화자 발화가 "프린트"이므로 Whisper prompt로는 해결 불가.~~ → **Vision 프롬프트 v5.4에서 코드-음차 대응 교정 명시로 해결.** / **Delta-05에서 gpt-5.4 Vision으로도 해결 확인.**
2. **correction ON 시 T1 답변 함수 수 감소** — OFF에서 4개(input, split, int, len) → ON에서 2개(input, split). correction이 int/len 관련 세그먼트를 trim하거나 청킹 경계를 바꾸고 있을 가능성. 전/후 세그먼트 diff 분석 필요.
3. **T1/T2 RP=0.0 고착** — rerank score가 0.001~0.003 수준으로 낮아 관련 청크가 선별되지 않음. threshold 조정 또는 rerank OFF 실험으로 원인 분리 필요.
4. **T3 입력값 미추출** (Critical) — 정답 `70,80,90,100,99`가 영상 2:30 구간의 브라우저 `prompt()` 다이얼로그 안에만 등장한다. 다이얼로그는 화면 위에 오버레이되는 일시적 UI이므로 Vision 프레임 분석이 해당 텍스트를 코드/화면텍스트로 추출하지 못한다. 전사에도 발화가 없어 RAG 검색 대상 청크 자체가 부재한 상태. Vision 프롬프트에 다이얼로그·팝업 영역 텍스트 추출 지시 추가가 필요하다.
5. **T1 열거 분산 (Delta-05)** — 같은 gpt-5.4 조건에서 Run 1: 2개, Run 2: 5개. 재현성 확보를 위해 temperature=0+seed, v3-cot 프롬프트 + `<thinking>` 후처리, n≥2 반복 실험이 필요.
6. **v3-cot `<thinking>` 후처리 미완** — `app/qa/chat.py`에서 `<thinking>` 블록 regex 제거 후 AR 재측정 필요.

---

상세 분석:
- `experiments/01-vision-guided-correction/correction_off_vs_on_coding-tutorial.md`
- `experiments/02-vision-guided-correction-v2/correction_v1_vs_v2_coding-tutorial.md`
- `experiments/03-whisper-prompt-correction-v2/exp-report-delta-04.md`

---

## 8. app/ 3층 구조 개편

### 설명

단일 파일에 혼재하던 도메인 로직을 역할 기준 3층으로 분리했다.

```
route      → app/main.py
pipeline   → app/pipelines/{ingest_pipeline,qa_pipeline}.py
도메인      → app/ingest/{transcription,vision,correction,chunking,multimodal}.py
             app/qa/{retrieval,chat}.py
공유 도메인  → app/embedding.py
인프라/메타  → config/prompts/diagnostics/snapshot/supabase_utils/evaluation_utils.py
```

- `app/ingest/` 신설: `transcription_utils` · `vision_utils` · `correction_utils` → `_utils` 접미어 제거 후 이동
- `app/qa/` 신설: `retrieval_utils` · `chat_utils` → `qa/retrieval` · `qa/chat`
- `app/pipelines/` 신설: `qa_pipeline.py` + `ingest_pipeline.py` 분리 추출
- `app/media_utils.py` 해체 → `embedding.py` · `ingest/chunking.py` · `ingest/multimodal.py`

pytest 31 passed. compileall(app+evals) + 전 모듈 import 검증 완료.

---

## 9. LangSmith @traceable 정비

### 설명

LangSmith UI에서 "어떤 요청이 들어왔는지" 즉시 읽히도록 이름·run_type을 현업 관행 기준으로 통일했다.

**이름 규칙**:
- 루트: `{domain}.request` (예: `qa.request`, `ingest.request`)
- 묶음: `{domain}.{이름}` (예: `qa.retrieve`)
- 말단: `{domain}.{번호}_{동작}` (예: `qa.1_embed_query`)
- 계층: `{domain}.{부모번호}.{자식번호}_...` (예: `qa.3.1_rerank`)

이름은 함수명이 아닌 도메인 언어로 고정 — 함수 리팩토링 시 UI 필터·대시보드가 깨지지 않도록.

**run_type 정정**:
- `ingest.4_analyze_frame`: `tool` → `llm` (GPT-4V chat.completions)
- `ingest.5_correct`: `tool` → `llm` (교정 chat.completions)
- `qa.2_vector_search` → `qa.2.1_vector_search`: `retriever`로 타입 일치
- `qa.1_embed_query` / `ingest.8_embed_chunk`: `tool` → `embedding`

**문서 분리**: `.claude/rules/langsmith-관측.md`(트리 스냅샷·rule)와 `.claude/rules/app-구조.md`(3층 구조·명명 규칙)를 분리해 CLAUDE.md에 등록.

---

## 10. asyncio 이벤트 루프 해방 + Vision 프레임 병렬화

### 설명

`async def` 라우트 핸들러가 blocking I/O를 직접 호출해 uvicorn 이벤트 루프가 실제로는 차단되던 문제를 수정했다.

- `main.py`: 8개 route의 blocking 호출을 `asyncio.to_thread()`로 래핑
- `ingest_pipeline.py`: `_VISION_CONCURRENCY = 4` 상수 추가. `_analyze_frames_parallel()` — `ThreadPoolExecutor`로 프레임 동시 분석. 순차 for 루프를 병렬 처리로 교체.

### 예시

```python
# 이전 — blocking call이 이벤트 루프 차단
@app.post("/qa")
async def qa_endpoint(req):
    result = run_qa(req)   # blocking
    return result

# 이후 — to_thread로 스레드 풀에 위임
@app.post("/qa")
async def qa_endpoint(req):
    result = await asyncio.to_thread(run_qa, req)
    return result
```

---

## 11. 파일 업로드 스트리밍 수정

### 설명

업로드 핸들러가 파일 전체를 메모리에 적재하던 구조를 1MB 청크 스트리밍으로 교체했다. 대용량 영상 업로드 시 OOM 위험 제거.

```python
# 이후 — 1MB 청크 스트리밍
CHUNK_SIZE = 1024 * 1024
async with aiofiles.open(dest_path, "wb") as f:
    while chunk := await file.read(CHUNK_SIZE):
        await f.write(chunk)
```

---

## 12. RetrievalCfg 필드 rename

### 설명

`RetrievalCfg` 내 필드명의 중복·혼용을 해소했다.

| 이전 | 이후 | 이유 |
|------|------|------|
| `search_top_k` | `top_k` | `RetrievalCfg` 안에서 `search_` 접두어 중복 |
| `search_pre_rerank_k` | `rerank_pool_size` | 역할 명시 |
| `rerank_top_n` | `rerank_top_k` | `_k/_n` 혼용 해소, Cohere 내부 변수명과 분리 |

`chunk_segments` 함수명도 `segment_transcript` → `chunk_segments`로 변경 — 파일명(`chunking.py`), trace 이름(`chunk`), 반환값(`chunks`)과 일관화.

pytest 31 passed.

---

## 13. BM25 + RRF Hybrid Search

### 설명

Dense(vector) 검색이 놓치는 고유명사·숫자·희귀 토큰을 BM25로 보완하고 Reciprocal Rank Fusion으로 두 ranking을 병합한다.

**설계 근거**: vector similarity(0~1)와 BM25 score(unbounded)는 스케일이 달라 직접 가중합 불가 — 순위만 쓰는 RRF(k=60, 원 논문 권장값)로 스케일 문제 회피.

- `app/qa/bm25.py` 신설: `media_id` 내부 청크로 corpus 한정. 한글/영숫자 정규식 토크나이저 (형태소 분석기 미사용 — 외부 의존성 최소화).
- `app/qa/retrieval.py`: `_rrf_fuse()`, `_hybrid_search()` 추가. `use_hybrid=False` 시 vector-only 폴백.
- `RetrievalCfg`: `use_hybrid` / `hybrid_rrf_k` / `hybrid_bm25_top_k` 추가.

```ini
# .env
USE_HYBRID=true
```

```python
# RRF 병합 — 스케일 무관하게 순위만 사용
def _rrf_fuse(vector_hits, bm25_hits, k=60):
    scores = defaultdict(float)
    for rank, seg in enumerate(vector_hits):
        scores[seg["id"]] += 1 / (k + rank + 1)
    for rank, seg in enumerate(bm25_hits):
        scores[seg["id"]] += 1 / (k + rank + 1)
    ...
```

---

## 14. HyDE (Hypothetical Document Embeddings)

### 설명

쿼리를 LLM으로 "가상 답변"으로 변환해 임베딩한다. 원 쿼리와 정답 청크 간 어휘 격차(예: 쿼리의 고유명사 vs 청크의 지시어)가 있을 때 semantic 매칭 품질을 올리는 게 목적.

- `app/qa/hyde.py` 신설: `generate_hypothetical_answer()` (`qa.0_hyde` llm trace)
- `qa_pipeline`에 HyDE 단계 삽입. **BM25/rerank는 원 쿼리 유지** — HyDE 어휘가 BM25 sparse 매칭을 희석하는 것을 방지.
- LLM 실패 시 원 쿼리 fallback (파이프라인 중단 없음)
- `RetrievalCfg`: `use_hyde`, `hyde_prompt_version` 추가. `prompts.py`에 `HYDE_PROMPTS v1`.

**꽁꽁이 케이스 검증**: vector similarity 0.207 → 0.373, RRF rank 17 → 1 개선 확인.

```ini
USE_HYDE=true
```

```python
# qa_pipeline 흐름
query_for_embed = query
if cfg.retrieval.use_hyde:
    query_for_embed = generate_hypothetical_answer(query, ...)  # LLM 가상 답변
candidates = search_similar_segments(query_for_embed, ...)     # HyDE 임베딩으로 검색
# BM25는 원 쿼리 그대로
if cfg.retrieval.use_hybrid:
    bm25_hits = bm25_search(query, ...)                        # 원 쿼리 유지
```

---

## 15. LLM rerank + rerank_provider 스위치

### 설명

Cohere cross-encoder가 alias(쿼리의 고유명사 ↔ 청크의 지시어)를 해결 못하는 한계가 꽁꽁이 케이스에서 드러남. listwise LLM rerank로 대체 경로를 만들고 `RERANK_PROVIDER`로 `"llm"` / `"cohere"` 선택 가능하게 분기했다.

- `app/qa/llm_rerank.py` 신설: listwise rerank + JSON 파싱 + fallback (`qa.3.1_llm_rerank` llm trace)
- `retrieval.py` `_rank_candidates`에 provider 분기. Cohere trace 이름 `qa.3.1_rerank` → `qa.3.1_cohere_rerank`로 rename
- `RetrievalCfg`: `rerank_provider`, `llm_rerank_prompt_version` 추가. **기본값 `"llm"`** (env var `RERANK_PROVIDER=cohere`로 전환 가능)
- `prompts.py`에 `LLM_RERANK_PROMPTS v1`.

**꽁꽁이 쿼리 검증**: Cohere는 chunk 0 누락, LLM은 `[0,1,2]` 정확히 선택 → "2021년 겨울 한강" 정답 복원.

```ini
RERANK_PROVIDER=llm        # 기본값
# RERANK_PROVIDER=cohere   # Cohere 전환 시
```

---

## 16. Delta-05 실험: Vision 모델 업그레이드 (gpt-5.4)

### 설명

delta-04의 Critical 문제(T1 `print()` context 미포함)에 대해 Vision 모델만 `gpt-4o-mini` → `gpt-5.4`로 교체한 후 full fresh n=2 반복 실험.

**고정 조건**: openai whisper-1 / bge-m3 embed / rerank ON / correction OFF (delta-04 A 조건 유지)

| 실험 | Vision | T1 답변 함수 수 | print() 포함 | AR | GR | RP |
|------|--------|:---:|:---:|:---:|:---:|:---:|
| delta-04 A (baseline) | gpt-4o-mini | 4 | ✗ | 1.0 | 1.0 | 0.0 |
| delta-05 Run 1 | gpt-5.4 | 2 | **✓** | 0.7 | 1.0 | 0.0 |
| delta-05 Run 2 | gpt-5.4 | 5 ✅ | **✓** | 0.7 | 1.0 | 0.0 |

**핵심 발견**:
- `print()` 누락 문제 해결. gpt-5.4는 두 Run 모두 `print()`를 포함.
- Run 2는 gold answer 5개(print, input, split, int, len)를 정확히 열거 — delta-04가 해결하지 못한 Critical 문제의 첫 해결 사례.
- 같은 조건 n=2 반복에서 T1 답변이 2개 ↔ 5개로 분산 재현. n=1 단일 실행만으로 성급히 결론 낼 위험 재확인.
- description 총 글자수 2.1배(4,705 → 9,872), `print(` 등장 프레임 4/10 → 10/10.

상세 분석: `experiments/04-vision-model-upgrade-gpt5-4/exp-report-delta-05.md`

---

## 17. QA 프롬프트 v3-cot

### 설명

T1 열거 문제(답변 함수 수 분산)를 프롬프트 레벨에서 개선하기 위해 CoT 3단계 구조를 도입했다.

**Collect → Curate → Compose** — 레버 3(regex 기반 호출 목록 주입)의 원리를 도메인 중립 패턴으로 일반화.

- `app/prompts.py`: `QA_SYSTEM_PROMPTS["v3-cot"]` 신규 등록 + `CURRENT_QA_SYSTEM_VERSION = "v3-cot"` 갱신
- 결과 (n=1): AR 1.00 / GR 0.94 / RP 0.47 — delta-05 Run 1/2(AR 0.88) 대비 대폭 상승

**주의**: `<thinking>` 블록이 후처리 없이 `answer`에 포함되어 judge에 전달됨 → AR=1.00이 답변 품질 개선인지 judge 가산 효과인지 분리 불가. `app/qa/chat.py`에서 `<thinking>` 제거 후처리 + n≥2 반복이 다음 단계.

---

## Retrieval 개선 실험 요약

**기준 케이스**: 꽁꽁이 영상 — 쿼리 "꽁꽁이가 처음 발견된 연도와 상황은 무엇인가요?" (정답 청크 = chunk 0)

**3층 동시 실패**: Vector(semantic 유사도 낮음) · BM25(조사 토큰 불일치) · Cohere rerank(alias 해결 불가) 세 층 모두에서 chunk 0이 탈락하는 구조적 문제였다.

| 실험 단계 | 변경 | chunk 0 결과 |
|------|------|------|
| Baseline (vector only) | — | similarity 0.207, RRF rank 17 |
| + Hybrid (BM25+RRF) | `USE_HYBRID=true` | BM25 개선 제한적 (조사 토큰 불일치) |
| + HyDE | `USE_HYDE=true` | similarity 0.373, RRF rank 1 (**vector 해결**) |
| + LLM rerank | `RERANK_PROVIDER=llm` | `[0,1,2]` 정확히 선택 (**alias 해결**) |

**최종 확인 조합**: HyDE + Hybrid + LLM rerank → 꽁꽁이 정답 복원.

**남은 과제**:
- HyDE 출력 분산 (동일 쿼리에서 가상 답변이 달라져 recall 편차 발생)
- BM25 한국어 조사 문제 (형태소 분석 미도입)
- LLM rerank 쿼리당 추가 LLM 호출 비용
- Chunk enrichment 미시도 (인덱싱 시점 메타 주입)

상세 분석: `notes/02_retrieval-개선-방향-탐색-및-실험.md`

---

## 18. LangSmith orphan root 수정

### 설명

`_analyze_frames_parallel()`에서 `ThreadPoolExecutor` 워커가 메인 스레드의 `contextvars`를 자동 상속하지 않아, `ingest.4_analyze_frame`이 `ingest.vision` 아래로 붙지 못하고 독립 루트로 찍히던 문제를 수정했다.

**발견 경위**: LangSmith UI에서 `ingest.vision` span이 465s인데 자식으로 보이는 `ingest.3_extract_frames`는 6s — 459s 갭이 설명되지 않아 추적.

**수정 내용**:
- `langsmith.run_helpers.get_current_run_tree()`로 메인 스레드에서 부모 run 캡처
- 각 워커 호출에 `langsmith_extra={"parent": parent_run}`으로 명시 전달

```python
# ingest_pipeline._analyze_frames_parallel
parent_run = get_current_run_tree()   # 메인 스레드에서 캡처

def _worker(frame):
    return analyze_frame_with_vision_model(
        ...,
        langsmith_extra={"parent": parent_run},  # 워커에 부모 전달
    )
```

사례는 `CLAUDE.md` 실수 로그와 `.claude/rules/langsmith-관측.md` §7 냄새 신호에 기록.

---

## 19. LangSmith run·Supabase metadata에 config snapshot 부착

### 설명

기존에는 실행 config가 `job_store`에만 남아 LangSmith UI나 Supabase에서 "어떤 설정으로 돌았는지" 역추적이 불가능했다. `run_ingest` / `run_qa` 루트 run의 inputs + metadata와 `save_media_file` metadata에 config snapshot을 함께 기록하도록 통일했다.

- `app/diagnostics.py` — `_trace_*` helper 초입에서 `get_config_snapshot()`을 run inputs·metadata로 주입
- `app/pipelines/ingest_pipeline.py` · `qa_pipeline.py` — snapshot을 Supabase metadata에도 저장
- `save_media_file` metadata shape: `{"source": "app" | "evals", "config": {...}}`로 통일

```python
# run 시작 시 config 자동 기록
run_tree.inputs = {
    "request": payload,
    "config": get_config_snapshot(),   # 추가
}
run_tree.metadata = get_config_snapshot()
```

---

## 20. evals/ 동결 harness 반영

### 설명

evals/ 내부 버그로 인한 동결 상태를 harness 레이어까지 반영했다. 에이전트가 매 작업마다 evals/를 자동 참조하는 경로를 차단하는 것이 목적.

- `CLAUDE.md` 상단에 동결 notice(섹션 0) 추가. 규칙·절대 금지·디렉토리 구조에서 evals 참조 정리
- `실험-프로토콜.md`: paths에서 `evals/**` 제거 (`experiments/**`만 유지), 상단에 동결 표기
- `harness-scanner.md`: 스캔 범위에서 `evals/` 제외

데이터(`evals/results/`, `evals/fixtures/`, `evals/datasets/`)는 보존. 동결 해제 시 섹션 0 삭제 + paths 복원.

---

## Vision 프롬프트 v6-scene

### 설명

코딩 강의 외 일반 영상(실외·사람·사건 등)에 적합한 Vision 프롬프트를 추가했다. v5-code가 `[코드]` · `[실행결과]` 등 코딩 도메인 특화 태그를 사용했던 것과 달리, v6-scene은 장면·인물/사물·이벤트·텍스트 4개 태그로 도메인 중립 구조를 제공한다.

| 버전 | 목적 | 구조 태그 |
|------|------|-----------|
| v5-code | 코딩 강의 | `[코드]` `[실행결과]` `[화면텍스트]` `[키워드]` |
| **v6-scene** | **일반 영상** | `[장면]` `[인물/사물]` `[이벤트]` `[텍스트]` |

`CURRENT_VISION_VERSION = "v6-scene"`으로 기본값 변경.

### 예시

```python
VISION_PROMPTS["v6-scene"] = (
    "이 프레임은 영상의 {timestamp:.1f}초 지점입니다.\n"
    "[장면] 어디서 무슨 일이 일어나고 있는지 1~2문장으로 설명하세요.\n"
    "[인물/사물] 화면에 등장하는 사람·차량·동물·주요 사물과 위치·행동을 구체적으로 서술하세요.\n"
    "[이벤트] 충돌·낙상·급정거·이상 행동 등 주목할 만한 사건이 있으면 명확하게 기술하세요. 없으면 '없음'.\n"
    "[텍스트] 화면에 보이는 자막·간판·표지판 등을 그대로 옮기세요. 없으면 '없음'."
)
```

---

## 19. 프레임 추출 개선 (동적 간격 · temperature=0 · 타임스탬프 포함 저장)

### 설명

짧은 영상에서 `frames_per_minute` 설정 기준으로 추출 시 프레임 수가 너무 적게 나오는 문제와, Vision 분석 결과의 재현성·검색성 문제를 함께 수정했다.

**동적 간격 조정**: 영상 길이 기준으로 `min_frames`(기본값 3)보다 적게 추출될 경우 간격을 자동으로 줄여 최소 프레임 수를 보장.

```python
if duration > 0 and duration / interval_sec < min_frames:
    interval_sec = duration / min_frames  # 자동 조정
```

**temperature=0**: Vision 분석 호출에 `temperature=0` 추가. 동일 프레임에 대해 반복 호출 시 출력이 달라지던 분산 문제 완화.

**타임스탬프 포함 저장**: 청크의 `frame_desc`에 여러 프레임 설명을 저장할 때 각 프레임의 타임스탬프를 `[1분 15초]` 형식으로 앞에 붙여 저장. 임베딩 검색 시 "어느 시점 장면인지"를 context에서 직접 확인 가능.

```python
# 이전 — 첫 번째 매칭 프레임 하나만
frame_desc = next((f["description"] for f in frame_analyses if ...), None)

# 이후 — 구간 내 전체 프레임, 타임스탬프 포함
matched_frames = [f for f in frame_analyses if chunk["start"] <= f["timestamp"] <= chunk["end"]]
frame_desc = "\n".join(
    f"[{_fmt_ts(f['timestamp'])}] {f['description']}" for f in matched_frames
) if matched_frames else None
```

`frames_per_minute`는 별도 커밋에서 3 → 10으로 상향 조정.

---

## 20. Vision 프롬프트 v6-talkshow-visual

### 설명

영화 월드컵 같은 다인 대담·시각 자료 풍부 영상을 위한 범용 비전 프롬프트를 신설했다. v6-scene이 실외·사람·사건 중심이었다면, v6-talkshow-visual은 스튜디오 대담·이미지 자료 중심 영상에 최적화된다.

| 버전 | 목적 | 구조 태그 |
|------|------|-----------|
| v5-code | 코딩 강의 | `[코드]` `[실행결과]` `[화면텍스트]` `[키워드]` |
| v6-scene | 일반 영상 | `[장면]` `[인물/사물]` `[이벤트]` `[텍스트]` |
| **v6-talkshow-visual** | **다인 대담·시각 자료** | `[인물]` `[시각 자료]` `[화면 텍스트]` `[구도·액션]` |

- baseline(v5-code) 0/3 → v6-talkshow-visual 2/3 통과
- `CURRENT_VISION_VERSION`을 `v6-scene → v6-talkshow-visual`로 전환

---

## 21. Vision 모델 다운그레이드 실험 (gpt-5.4 → gpt-4o) + Concurrency 조정

### 설명

비용 절감을 위해 gpt-5.4 → gpt-4o 다운그레이드 실험을 진행했다.

| 태스크 | gpt-5.4 | gpt-4o | 결론 |
|--------|:-------:|:------:|------|
| V1 펄프픽션 식별 | ✓ | ✗ (후퇴) | gpt-5.4 필요 |
| V2 안경 카운트 | ✓ | ✓ | gpt-4o 가능 |
| V3 레보스키 | ✓ | ✓ | gpt-4o 가능 |
| **전체 통과율** | **3/3** | **1/3** | — |

- "엉뚱한 영화로 확신 있게 답변"하는 새 failure mode 발견
- Track 3/4 실험은 gpt-5.4 유지로 결론

**Vision concurrency 조정**: gpt-4o 전환 시 4-worker 동시 호출이 OpenAI TPM rate limit 초과로 ingest 실패 → `_VISION_CONCURRENCY = 4 → 2`로 하향, 안정성 우선.

---

## 22. 시멘틱 청킹 구현

### 설명

Track 2까지는 고정 30초 윈도우로 청킹했으나, baseline 분석에서 토픽 경계와 어긋나는 케이스(C1, C4)가 반복 확인돼 segment 임베딩 기반 경계 탐지를 추가했다.

**Phase 1 — 스캐폴딩**
- `Config` / `EmbeddingCfg`에 `chunking_strategy`, `semantic_breakpoint_percentile`, `semantic_min_chunk_seconds` 3필드 추가
- 기본값 `fixed`라서 기존 실험 경로 동작 불변
- `chunk_segments()`에 strategy 분기 추가, 기존 sliding window는 `_chunk_fixed()`로 추출

**Phase 2 — 실구현**
- segment 임베딩 → 인접 코사인 거리 → percentile 기준 경계 판정 → min_seconds 제약 후 병합
- helper 4개 분리 추출: `_adjacent_cosine_distances`, `_cosine_similarity`, `_percentile`, `_merge_by_boundaries`
- numpy 없이 stdlib `math`만 사용. 스모크 테스트 4종 통과
- `embed_segment_for_boundary` 래퍼 추가 — chunk 임베딩과 맥락 분리

**버그 픽스**: `get_config_snapshot()`이 신규 3필드를 내보내지 않아 실험 결과 JSON에 청킹 전략 정보가 빠지는 문제 수정 ("기록 = 실행" 원칙 위반).

### 예시

```python
# chunking_strategy = "semantic"일 때 흐름
distances = _adjacent_cosine_distances(embeddings)
boundaries = [i for i, d in enumerate(distances) if d > _percentile(distances, breakpoint_percentile)]
chunks = _merge_by_boundaries(segments, boundaries, min_chunk_seconds)
```

```ini
# .env
CHUNKING_STRATEGY=semantic
SEMANTIC_BREAKPOINT_PERCENTILE=90
SEMANTIC_MIN_CHUNK_SECONDS=15
```

---

## Retrieval 실험 E·F (대조 실험)

### 실험 E — use_rerank=False + threshold 모드

LLM rerank를 제거하고 RRF top-k를 threshold 필터로만 선별.

| 항목 | 값 |
|------|---|
| `use_hyde` | True |
| `use_hybrid` | True |
| `use_rerank` | **False** |
| `search_threshold` | 0.3 |
| `top_k` | 3 |

- `vec_limit = top_k = 3` → chunk 0(sim ~0.37)이 vector top-3 진입 불가
- chunk 0 RRF rank: 6위. `similarity` 필드 없어 threshold 0 판정 → 탈락
- 최종 답변: **연도 누락, 실패**. Latency: **6.6초** (실험 D LLM rerank 대비 -8초)

**실험 D(LLM rerank)와 차이**:
1. vec_limit: rerank=True → 15개 pool, rerank=False → 3개 pool
2. BM25 출신 chunk는 `similarity` 필드 없어 threshold 필터에서 무조건 탈락
3. LLM은 alias("꽁꽁이=한강 고양이") 맥락 추론 가능, threshold 수치 필터는 불가

### 실험 F — Cohere rerank + kiwipiepy 형태소 분석

BM25 토크나이저를 공백 분리 → kiwipiepy 명사 추출(NNG·NNP·SL 등)로 교체했을 때 변화 확인.

| 토크나이저 | 쿼리 토큰 | chunk 0 BM25 점수 | chunk 0 RRF rank |
|---|---|:---:|:---:|
| 기존 (공백 분리) | `['꽁꽁이가', '처음', ...]` | 0.000 | 1위 |
| kiwipiepy | `['처음', '발견', '해', '상황']` | 0.000 | **4위** (하락) |

- 두 경우 모두 chunk 0 BM25 점수 0.000 — 공백 분리는 조사 불일치, kiwi는 "꽁꽁이" 미등록 고유명사 드롭
- kiwipiepy가 오히려 다른 청크를 상위로 올려 chunk 0 RRF rank 하락
- Cohere rerank 탈락 동일 → 최종 **실패**

**결론**: "꽁꽁이" 같은 미등록 고유명사는 kiwipiepy에서 드롭되어 BM25 고유명사 매칭 강점을 잃음. 이 케이스의 근본 병목은 Cohere alias 해결 불가로, 토크나이저 교체로는 해결 불가.

---

## Track 4 — 화자 주석 (Speaker Annotation)

### 배경

영화 월드컵 토크쇼 영상처럼 다수 화자가 등장하는 컨텐츠에서는 "김민경이 뭐라고 했나요?" 류의 화자 특정 쿼리가 중요하다. Track 4 baseline 실험에서 pitch/speaker 메타 부재로 화자 특정 질문(E1~E4) 전체 실패가 확인됨 (`notes/03_영화-월드컵-실험-질문셋.md`).

### 설명

화자 정보를 청크·문서 두 레벨에 주입하고, HyDE·LLM rerank 프롬프트가 이를 인지하도록 파이프라인을 확장했다. 임베딩 재생성 없이 컬럼 추가·후처리 경로만으로 구현해 기존 인덱싱 결과를 그대로 활용한다.

**저장 구조**:

| 레벨 | 위치 | 역할 |
|------|------|------|
| 청크 | `media_segments.speaker_id` (nullable text) | 각 발화의 화자 → `context_text` `(화자)` 접두어 |
| 문서 | `media_files.metadata.speakers` (JSONB 배열) | 영상 출연자 리스트 → HyDE/rerank 프롬프트 `{speaker_intro}` 주입 |

**구현 목록**:

1. **Schema** (`migrations/001_add_speaker_id.sql`): `media_segments.speaker_id TEXT` 컬럼 추가
2. **Supabase helpers** (`app/supabase_utils.py`): `get_media_speakers`, `update_segment_speaker` 등 추가
3. **라벨링 CLI** (`experiments/track4-speaker-annotation/annotate_speakers.py`): GPT로 청크별 화자 판정 후 청크·문서 양 레벨에 기록. `--sync-metadata`로 기존 청크에서 backfill 가능
4. **Prompts** (`app/prompts.py`): `HYDE_PROMPTS["v2-speaker"]` / `LLM_RERANK_PROMPTS["v2-speaker"]` — `{speaker_intro}` 자리표시자로 출연자 리스트를 주입. `hyde_prompt_uses_speakers` / `llm_rerank_prompt_uses_speakers` 헬퍼로 호출자가 speaker fetch 필요 여부를 판단
5. **QA pipeline 통합**: 프롬프트 템플릿에 `{speaker_intro}`가 있을 때만 `get_media_speakers` 호출 — baseline v1 경로엔 DB 오버헤드 없음. `context_text`에 `(화자) ` 접두어 부착

```python
# annotate_speakers.py — dry-run
pipenv run python experiments/track4-speaker-annotation/annotate_speakers.py \
    --media-id <uuid> \
    --dry-run

# context_text 예시 (speaker_id 있을 때)
"(김민경) 저는 펄프픽션이 가장 기억에 남아요."
```

```ini
# .env — v2-speaker 프롬프트로 전환
HYDE_PROMPT_VERSION=v2-speaker
LLM_RERANK_PROMPT_VERSION=v2-speaker
```

**설계 결정**:
- `match_segments` RPC 미수정 — 검색 결과에 `speaker_id`를 후속 enrich하는 방식
- `text`, `embedding` 필드 불변 — 임베딩 재생성 없음
- 기본값은 `v2-speaker`로 전환됨 (이 커밋부터 `/qa` 응답이 화자 인지 경로로 동작)
