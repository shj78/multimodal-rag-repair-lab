# Multimodal RAG Failure Repair Lab

영상 기반 QA 시스템에서 실제로 깨지는 지점을 추적하고, 검색 파이프라인과 메타데이터 설계를 고쳐 답변 품질을 복원한 실험 기록입니다.

이 레포는 Sprint 4 과정 산출물을 포트폴리오 형태로 정리한 것입니다. 단순히 모델을 바꾸는 대신, ASR, vision, correction, chunking, retrieval, rerank, QA context 중 어느 레이어에서 문제가 생겼는지 분리해서 확인했습니다.

## Portfolio Cases

| Case | Problem | Fix | Result |
| --- | --- | --- | --- |
| `print()` Multimodal Parse | 화면에는 `print()`가 있지만 QA가 내장 함수 목록에서 누락 | Whisper prompt, vision-guided correction, gpt-5.4 frame analysis 비교 | 핵심 질문에서 4/5 함수 복원 -> 5/5 함수 복원 |
| CCTV Visual QA | 짧은 블랙박스 영상에서 음성보다 화면 장면이 답변 근거가 됨 | v6-scene vision prompt와 timestamped context로 장면 근거 저장 | 인물 접근 장면을 grounded answer로 복원 |
| Speaker-Aware Movie Debate | 39분 토론에서 "누가 말했는가"가 검색 결과에서 사라짐 | `speaker_id` schema, speaker metadata, HyDE/rerank/context speaker integration | "맥빠지는 느낌" 발화자를 허키로 정정 |

## Demo Site

Next.js로 만든 포트폴리오 데모는 `demo-site/`에 있습니다.

```bash
cd demo-site
pnpm install
pnpm dev --hostname 0.0.0.0 --port 3001
```

브라우저에서 엽니다.

```text
http://127.0.0.1:3001/
```

정적 빌드 확인:

```bash
cd demo-site
pnpm build
```

## Backend App

FastAPI 기반의 멀티모달 ingest/QA 파이프라인입니다.

```bash
pipenv install --dev
cp .env.example .env
pipenv run uvicorn app.main:app --reload
```

주요 API:

| Endpoint | Purpose |
| --- | --- |
| `POST /media/upload` | 영상 업로드 후 전사, 프레임 분석, chunk 저장 |
| `POST /qa` | media_id와 질문으로 grounded QA 실행 |
| `GET /media/{media_id}/segments` | 저장된 segment/context 확인 |
| `GET /media/{media_id}/evaluate` | QA 평가 실행 |

## Architecture

```text
Video upload
  -> audio transcription
  -> frame vision analysis
  -> optional transcript correction
  -> semantic/fixed chunking
  -> embedding + hybrid retrieval
  -> optional HyDE
  -> optional LLM rerank
  -> grounded QA
  -> judge/evaluation
```

Speaker-aware case:

```text
media_segments.speaker_id
media_files.metadata.speakers
  -> speaker_intro for HyDE/rerank prompts
  -> speaker-prefixed answer context
```

## Repository Map

| Path | Description |
| --- | --- |
| `app/` | FastAPI app, ingest pipeline, QA pipeline, retrieval modules |
| `app/ingest/` | transcription, vision analysis, correction, chunking |
| `app/qa/` | retrieval, BM25, HyDE, LLM rerank, chat answer generation |
| `experiments/` | experiment logs and reports for each failure-repair run |
| `experiments/track4-speaker-annotation/` | speaker annotation CLI and schema migration |
| `docs/track-b/` | Track B reports, implementation notes, PR summary |
| `demo-site/` | public-facing portfolio site |
| `tests/` | focused regression tests |

## Verification

```bash
pipenv run pytest
cd demo-site && pnpm build
```

Recent public-demo checks:

- `demo-site` production build generates only 3 experiment pages: `print`, `cctv`, `movie`.
- Removed Case 4 route returns 404.
- `.env` is ignored; only `.env.example` is tracked.

## Public Data Policy

Runtime uploads, extracted frames, `.env`, and large local media files are intentionally excluded from the public repository.

The 39-minute source video used for the speaker-aware movie debate case is not committed because it is large and may have external content rights. The README and demo text document the pipeline and evidence path; local media files can be placed under `demo-site/public/media/` when running a private local demo.

## Tech Stack

- Python 3.11
- FastAPI
- Supabase
- Whisper / faster-whisper
- OpenAI vision, chat, and embedding models
- BM25 + hybrid retrieval
- HyDE and LLM reranking
- Next.js 14 + Tailwind CSS
