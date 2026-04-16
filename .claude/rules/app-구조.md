---
description: app/ 구조 규칙. route/pipeline/util 3층, 폴더 레이아웃, 명명 규칙, 용어 주의.
paths:
  - "app/**"
---

# app/ 구조 규칙

> app/ 코드의 배치·명명·분할 규칙.
> 루트 CLAUDE.md의 "변경에는 맥락이 따라다닌다" 원칙을 코드 구조에서 구현한 것.
> LangSmith `@traceable` 부착은 별도 문서(`langsmith-관측.md`)를 참조. 이 문서는 관측 없이도 성립하는 구조 규칙만 담는다.

---

## 0. 관측과의 연결

이 문서의 구조 규칙 상당수가 LangSmith trace 토폴로지에 직접 반영된다. 구조를 바꿀 때는 `langsmith-관측.md`를 **함께 확인**하고 필요 시 갱신한다.

| 구조 변경 | 관측 영향 | 갱신할 곳 |
| --- | --- | --- |
| 도메인 추가 (ingest/qa 외) | trace prefix 신설 (`{domain}.`) | `langsmith-관측.md` §2, §6 스냅샷 |
| 새 pipeline `run_*` 추가 | 새 root run (`{domain}.request`) | `langsmith-관측.md` §6 스냅샷 |
| `_trace_*` grouping helper 추가·변경 | chain run 토폴로지 변경 | `langsmith-관측.md` §6 스냅샷 |
| util 신설/이동 | 부착 대상 레이어 재판단 | `langsmith-관측.md` §4 부착 원칙 |
| 1:1 래퍼 제거 | 빈 `chain` 노드 제거 효과 | `langsmith-관측.md` §4 |

---

## 1. 3층 원칙 (route / pipeline / util)

| 층 | 위치 | 역할 |
| --- | --- | --- |
| **route** | `main.py` | HTTP 입출력. 요청 수신·응답 반환·job_store 갱신 |
| **pipeline** | `pipelines/*.py` | 흐름 오케스트레이션. 요청 1건의 처리 단위 |
| **util** | 도메인 폴더·공유 도메인·인프라 | 세부 작업. 부품 |

- route는 pipeline을 호출, pipeline은 util을 조합한다. 거꾸로 부르지 않는다.
- 오케스트레이션 로직이 route 파일에 섞이면 pipeline으로 추출한다.
- pipeline은 util을 **조합**만 한다. pipeline 끼리 서로 호출하지 않는다.

**왜**: 층이 섞이면 재사용·테스트·관측 경계가 모두 깨진다. 과거 `main.py:process_media_background`가 ingest 오케스트레이션을 직접 품고 있었을 때, `evals/_stages.py`가 같은 흐름을 재구현해 중복이 생겼다. `run_ingest` 추출 후 단일 경로가 됐다.

---

## 2. 폴더 레이아웃

```
app/
├── main.py                # route
├── pipelines/             # 흐름 (route ↔ util 사이 경계)
│   ├── qa_pipeline.py     # run_qa
│   └── ingest_pipeline.py # run_ingest
├── ingest/                # 도메인 — 미디어 처리
│   ├── transcription.py
│   ├── vision.py
│   ├── correction.py
│   ├── chunking.py
│   └── multimodal.py
├── qa/                    # 도메인 — 질의응답
│   ├── retrieval.py
│   └── chat.py
├── embedding.py           # 공유 도메인 (qa + ingest 양쪽이 호출)
├── config.py              # 인프라 — 설정
├── prompts.py             # 인프라 — 프롬프트
├── diagnostics.py         # 인프라 — 공용 측정
├── snapshot.py            # 인프라 — 실험 스냅샷
├── supabase_utils.py      # 인프라 — DB 접근
└── evaluation_utils.py    # 메타 — 평가 (qa 흐름 재현)
```

**배치 원칙**:

- **도메인 폴더** (`ingest/`, `qa/`): 도메인 전용 util 모음. 2+ 파일일 때 성립.
- **공유 도메인** (`embedding.py`): qa·ingest 양쪽이 호출하는 함수만 루트 단일 파일. 한쪽 도메인 폴더에 넣으면 반대쪽이 역방향 import가 된다.
- **인프라**: 모든 도메인이 호출하는 횡단 관심사. 도메인 폴더 안에 넣으면 역방향 import 냄새.
- **메타** (`evaluation_utils.py`): 평가용으로 qa 흐름을 재현하는 별종. 장기적으로 `run_qa` 호출로 일원화 예정이라 분리 보관.

**루트 파일 판단 기준**: "어느 도메인 폴더에도 못 들어가는가?" → 공유/인프라/메타 중 하나라면 루트.

---

## 3. 명명 규칙

### 함수 명명

| 패턴 | 역할 | 예 |
| --- | --- | --- |
| **`run_*`** | pipeline의 public entrypoint. route·evals 같은 외부가 호출 | `run_qa`, `run_ingest` |
| **`_trace_*`** | pipeline 내부 private grouping helper. 여러 leaf를 묶는 용도. **목적은 trace tree grouping** — 상세는 `langsmith-관측.md` §4 예외 조항 | `_trace_transcribe`, `_trace_vision`, `_trace_embed` |
| **leaf util** | 자유 명명. 관측 이름(trace name)과 1:1 강제 없음 | `get_answer_by_chat_model`, `search_similar_segments` |

- `run_*`는 **외부에서 호출되는 흐름 진입점**에만 쓴다. pipeline 내부의 보조 함수는 `run_*` 쓰지 않는다.
- `_trace_*`는 grouping만이 역할인 private 헬퍼. 외부 계약이 아니므로 public 경로로 노출하지 않는다.
- leaf util의 Python 함수명은 **코드 내부 안정성 우선**. 관측만의 이유로 이름 바꾸지 않는다.

**왜**: `run_*`는 원본 코드(`evals/_stages.py`)가 이미 쓰던 언어. 새 철학 도입이 아니라 기존 언어를 app에도 가져온 것. `_trace_*` prefix는 "이건 grouping 전용이지 business 함수가 아니다"를 이름 한 줄로 드러낸다.

### 파일 명명

- **도메인 폴더 안**: `_utils` 접미어 **제거**. 폴더 이름이 이미 도메인 의미를 운반하므로 `retrieval.py`, `chat.py`, `transcription.py`로 충분.
- **루트 인프라·메타**: `_utils` 접미어 **유지**. `supabase_utils.py`, `evaluation_utils.py`. 관례 일관성과 rename diff 최소화.

**왜**: 도메인 폴더 안에서 `_utils` 접미어는 "qa 안에 qa-related util"을 이중 표현. 폴더가 이미 운반하는 정보를 파일명이 반복.

---

## 4. 용어 주의 — 피해야 할 단어

폴더명·변수명·문서에서 **쓰지 않는다.**

| 단어 | 왜 피하는가 |
| --- | --- |
| **`stage`** | 업계마다 크기 해석이 달라 외부 소통에 위험. 작은 내부 단위로도, 큰 덩어리로도 쓰임. |
| **`step`** | LangSmith run 트리의 원자 단위(`vector_search` 같은 함수 1회 호출)를 가리키는 관측 용어. 폴더명으로 쓰면 두 층을 동시에 지시. |
| **`service`** | SOA/마이크로서비스를 연상시켜 경계·배포 단위 오해. 우리가 쓰는 건 **파이프라인**이지 서비스가 아님. |
| **`util/` 폴더** | 3층 원칙의 `util` 층을 폴더로 또 만들면 `ingest/`가 이미 운반하는 의미를 중복 표현. 정보량 0 계층. |

**채택 언어**: `pipeline`, `util`(개념 층 명칭으로만), 도메인명(`ingest`, `qa`). 새 도메인 추가 시 **소문자 단수형**.

**왜**: 이 단어들은 설계 논의 과정에서 검토되고 기각된 후보다. 같은 논의가 반복되지 않도록 규칙에 박제. 팀 외부와 소통할 때도 용어 혼선을 줄인다.

---

## 5. 신설·분할 기준

### 폴더 신설

- **파일 2+ 일 때만.** 1파일 폴더는 import 경로만 늘리고 의미 없다.
- 과거 `qa_pipeline.py` 혼자였을 때 `pipelines/` 폴더를 안 만들었고, `ingest_pipeline.py`가 추가되어 2파일이 되면서 비로소 폴더 성립.

### 파일 분할

한 파일이 **역할 2+ 개를 담고 있고 파일명이 그 둘을 동시에 설명하지 못할 때** 분할한다.

- 과거 `media_utils.py`가 "텍스트 청킹 + 멀티모달 합성 + 공유 임베딩" 3역을 담고 있었음. `media`라는 단어가 셋 모두를 설명하지 못해 `chunking.py` + `multimodal.py` + `embedding.py`로 분할.
- 판단 기준: **파일명이 역할을 구체적으로 설명하는가.** 모호한 상위어(media, common, shared)로 묶이면 분할 신호.

### 도메인 추가

- 기존 `ingest` / `qa` 어느 쪽에도 자연스럽게 안 들어갈 때만 새 도메인 폴더.
- 판단 증거: pipeline·route 양쪽에서 호출되는가. 한 곳에서만 쓰면 util로 충분.

---

## 6. 1:1 래퍼 금지

public 함수가 단일 util 호출만 감싸는 경우 래퍼를 두지 않는다.

- 과거 `run_generate`가 `get_answer_by_chat_model` 하나만 호출 → 제거.
- `run_embedding`을 public으로 올리지 않음 — retrieve 내부 단계일 뿐 독자 use case 아님.
- public 경계는 **여러 util의 조합** 또는 **의미 있는 오케스트레이션**이 있을 때만 만든다.

**왜**: 1:1 래퍼는 경계만 늘리고 정보 추가가 없다. 리팩토링 시 불필요한 diff, 호출 경로 추적 비용 증가.

**관측 측면의 영향**은 `langsmith-관측.md`에서 별도로 다룬다 (의미 없는 `chain` 노드가 trace tree에 추가되는 문제).

---

## 7. 냄새 신호

- route 파일(`main.py`)에 오케스트레이션 로직이 길게 들어 있다 → pipeline 추출
- 1파일만 있는 폴더가 있다 → 폴더 해체 또는 2번째 파일 추가 후 성립 재확인
- 파일명이 상위어(media, common, shared)로 모호하다 → 분할 후보
- 도메인 폴더 안 파일에 `_utils` 접미어가 붙어 있다 → 제거
- `stage`, `step`, `service`가 폴더·변수명으로 등장한다 → §4 재확인
- pipeline 함수가 단일 util만 호출한다 → 1:1 래퍼, 제거 검토
- 새로 만든 public 함수가 `run_*` 아닌 이름이다 → pipeline entrypoint인지 재확인

---

## 8. 변경 원칙

- 구조 변경은 **동작 변경과 한 커밋에 섞지 않는다** (루트 CLAUDE.md §4).
- 폴더 이동은 import 깨짐 없이 검증 가능한 원자 단위로 쪼개 커밋한다.
- 규칙을 추가·변경할 때는 **왜 추가하는지 한 줄**과 **적용 시 체크할 것**을 함께 적는다.
