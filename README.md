# Multimodal RAG Failure Repair Lab

[Live Demo](https://shj78.github.io/multimodal-rag-repair-lab/) · [Demo Source](./demo-site) · [Speaker Annotation](./experiments/track4-speaker-annotation)

멀티모달 QA 시스템에서 실제로 부딪혔던 기록을 추적하고, 검색 파이프라인과 메타데이터 설계를 고쳐 답변 품질을 복원한 실험 기록입니다.

팀 프로젝트로 진행되었고, 프로젝트 과정 동안 산출물을 포트폴리오 형태로 정리했습니다.

모델 버전을 높이려고 하기보다 ASR, vision, correction, chunking, retrieval, rerank, QA context 중 어느 레이어에서 문제가 생겼는지 분리해서 확인했습니다.

## 데모페이지

포트폴리오 페이지는 GitHub Pages로 배포했습니다.

```text
https://shj78.github.io/multimodal-rag-repair-lab/
```

로컬에서 확인하려면 아래와 같이 테스트가 가능하고, 영상을 확인할 수 있습니다.

```bash
cd demo-site
pnpm install
pnpm dev --hostname 0.0.0.0 --port 3001
```

## 실험한 케이스

| 케이스 (Case) | 문제 (Problem) | 수정 (Fix) | 결과 (Result) |
| --- | --- | --- | --- |
| `print()` Multimodal Parse | 파이썬 강의 화면에는 `print()`가 있지만 QA가 내장 함수 목록에서 누락되던 문제 | Whisper prompt, vision-guided correction, gpt-5.4 frame analysis 비교 | 핵심 질문에서 4/5 함수 복원 -> 5/5 함수 복원 |
| CCTV Visual QA | 짧은 블랙박스 영상에서 음성보다 화면 장면이 답변 근거가 되었지만 화면 장면이 분석 프레임에 담기지 않았던 문제 | v6-scene vision prompt와 timestamped context로 장면 근거 저장 | 인물 접근 장면을 grounded answer로 복원 |
| Speaker-Aware Movie Debate | 39분 다자 토론에서 "누가 말했는가"가 검색 결과에서 사라져 결과가 정확하게 나오지 않은 문제 | `speaker_id` schema, speaker metadata, HyDE/rerank/context speaker integration | "맥빠지는 느낌" 발화자를 허키로 정정 |


## 백엔드

FastAPI 기반의 멀티모달 ingest/QA 파이프라인으로 구축했습니다.

```bash
pipenv install --dev
cp .env.example .env
pipenv run uvicorn app.main:app --reload
```

주요 API:

| 엔드포인트 (Endpoint) | 기능 (Purpose) |
| --- | --- |
| `POST /media/upload` | 영상 업로드 후 전사(transcription), 프레임 분석(frame analysis), 청크 저장(chunk storage) |
| `POST /qa` | `media_id`와 질문으로 근거 기반 답변(grounded QA) 생성 |
| `GET /media/{media_id}/segments` | 저장된 구간(segment)과 답변 근거(context) 확인 |
| `GET /media/{media_id}/evaluate` | 질문 답변 결과 평가(QA evaluation) 실행 |

## 아키텍처

기본 파이프라인:
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

다자 발화의 경우 추가된 파이프라인:

```text
media_segments.speaker_id
media_files.metadata.speakers
  -> speaker_intro for HyDE/rerank prompts
  -> speaker-prefixed answer context
```

## 프로젝트 구조

| 경로 (Path) | 설명 |
| --- | --- |
| `app/` | FastAPI 앱, 수집 파이프라인(ingest pipeline), QA 파이프라인(QA pipeline), 검색 모듈(retrieval modules) |
| `app/ingest/` | 전사(transcription), 화면 분석(vision analysis), 전사 교정(correction), 청킹(chunking) |
| `app/qa/` | 검색(retrieval), BM25, HyDE, LLM 재정렬(LLM rerank), 답변 생성(chat answer generation) |
| `experiments/` | 실패 원인 분석과 개선 실험 로그(experiment logs), 결과 리포트(reports) |
| `experiments/track4-speaker-annotation/` | 화자 라벨링 CLI(speaker annotation CLI)와 스키마 변경(migration) |
| `docs/track-b/` | Track B 리포트, 구현 노트(implementation notes), PR 요약(PR summary) |
| `demo-site/` | 포트폴리오 데모 페이지(public-facing portfolio site) |
| `tests/` | 회귀 테스트(regression tests) |

## 검증

```bash
pipenv run pytest
cd demo-site && pnpm build
```

## 사용된 기술

- Python 3.11
- FastAPI
- Supabase
- Whisper / faster-whisper
- OpenAI 비전·채팅·임베딩 모델(vision, chat, embedding)
- BM25 + 하이브리드 검색(hybrid retrieval)
- HyDE와 LLM 재정렬(LLM reranking)
- Next.js 14 + Tailwind CSS
