# Track 4 Step 2 — 화자 주석 실험

> 설계: `notes/04_track4-화자-주석-계획.md`
> 대상 이슈: 영화 월드컵 질문셋(`notes/03_영화-월드컵-실험-질문셋.md`) E1~E4

---

## 현재 진행 상황

| Phase | 내용                             | 상태 |
| ----- | -------------------------------- | ---- |
| 1     | Supabase 스키마 확장             | 완료 |
| 2     | 화자 라벨링 스크립트             | 완료 |
| 3     | `update_segment_speaker()` 추가  | 완료 |
| 4     | `qa/chat.py` context_text 변경 + retrieval enrich | 완료 |
| 5     | HyDE 프롬프트 v2-speaker         | 완료 |
| 6     | LLM rerank 프롬프트 v2-speaker   | 완료 |
| 7     | `/qa` 엔드포인트 검증            | —    |

---

## Phase 1 실행 방법

1. **Supabase Dashboard** → 프로젝트 선택 → 좌측 메뉴 **SQL Editor** 진입.
2. `migrations/001_add_speaker_id.sql` 내용을 붙여넣고 **Run**.
3. 아래 확인 쿼리 실행:

   ```sql
   SELECT column_name, data_type, is_nullable
     FROM information_schema.columns
    WHERE table_name = 'media_segments'
      AND column_name = 'speaker_id';
   ```

   결과에 `speaker_id | text | YES` 한 행이 보이면 성공.

4. 기존 `media_segments` 행의 `speaker_id`는 NULL로 남아있다. Phase 2 스크립트가 채움.

---

## Phase 2 실행 방법

화자 후보는 `김간지 / 김민경 / 허키` 3인 고정 (스크립트 상단 `SPEAKERS` 상수).

### (권장) dry-run으로 미리 확인

```bash
pipenv run python experiments/track4-speaker-annotation/annotate_speakers.py \
    --media-id <uuid> \
    --dry-run
```

- 청크 로드 개수, 화자별 카운트 요약, 처음 5개 매핑 결과를 출력.
- DB는 건드리지 않음.

### 실제 저장

```bash
pipenv run python experiments/track4-speaker-annotation/annotate_speakers.py \
    --media-id <uuid>
```

- `update_segment_speaker`가 청크별로 DB 업데이트.
- 완료 후 Supabase에서 확인:
  ```sql
  SELECT speaker_id, COUNT(*)
    FROM media_segments
   WHERE media_id = '<uuid>'
   GROUP BY speaker_id;
  ```

### 옵션

- `--model` (기본 `gpt-4o`): OpenAI 모델명 변경.
- `--sync-metadata`: GPT 호출 없이 **기존 청크 `speaker_id`에서 집계**해 `media_files.metadata.speakers`만 업데이트. 이미 라벨링이 끝난 영상에서 문서 레벨 메타데이터만 backfill할 때 사용.
- 필요 시 `SPEAKERS` 리스트를 수정해 다른 영상에도 재활용 가능.

### 메타데이터 저장 구조

본 실행(`--dry-run` 없이)은 **두 레벨에 모두 기록**한다:

| 레벨 | 위치 | 역할 |
| ---- | ---- | ---- |
| 청크 | `media_segments.speaker_id` | 각 발화의 화자 — context_text의 `(화자)` 접두어 |
| 문서 | `media_files.metadata.speakers` (JSONB 배열) | 영상 출연자 리스트 — HyDE/rerank 프롬프트의 `{speaker_intro}` 주입 메타데이터 (SSoT) |

### 주의

- context window: 청크가 수백 개 이상이면 한 번의 GPT 호출로 처리 어려울 수 있음. 실행 후 `WARN: ... 라벨링 누락` 메시지가 뜨면 분할 호출 로직 추가 필요.
- 결과가 편중되면 (한 화자가 90% 이상) 프롬프트 보강 검토.

---

## 설계 주요 결정

- **임베딩 재생성 없음**: `speaker_id`는 별도 컬럼. `text`, `embedding` 필드 불변.
- **`match_segments` RPC 미수정**: RPC는 그대로 두고, 검색 결과에 speaker_id를 후속 enrich.
- **1회성 마이그레이션**: 기존 영상 1건에 대해 스크립트로 라벨링. `run_ingest` 경로 변경 없음.
