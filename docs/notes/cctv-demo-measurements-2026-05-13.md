# CCTV Demo Measurement — 2026-05-13

## 목적

`demo-site/src/lib/experiments.ts`의 03 CCTV 카드에 있던 더미 수치를 실제 FastAPI/Supabase 실행 결과로 교체하기 위한 측정 기록.

## 실행 상태

- Server: `http://127.0.0.1:8010`
- Media ID: `30fa5dfc-9298-4af3-be55-2ad8e197a8ed`
- Filename: `한문철_무단횡단.mp4`
- Status: `ready`
- Duration: `14.84s`
- Segment count: `1`

주요 config:

- Vision prompt: `v6-scene`
- Frames per minute: `10`
- Vision model: `gpt-4o`
- Embedding model: `text-embedding-3-small`
- QA model: `gpt-4o-mini`
- Chunking: `semantic`
- Hybrid: ON
- HyDE: ON
- LLM rerank: ON, prompt `v2-speaker`

## 근거 청크

- Segment ID: `89`
- Chunk index: `0`
- Transcript text: `아 알겠습니다 보배첨건설 제가 그거`
- Accepted source: `true` in all three QA calls

Vision `frame_description` 요약:

- `[4초]` 블랙박스 시점의 도심 도로. 녹색 신호등, 흰색 소형 화물차, 승용차, 상가, 가로수, 전신주가 보임. 화면 텍스트: `한문철TV`, `정직한포차`.
- `[9초]` 차량 앞 유리 바로 앞에 얼굴이 흐려진 사람이 가까이 다가와 차량 보닛 앞쪽에 몸을 숙이고 있음. 도로 앞쪽에는 승용차 몇 대, 좌측에는 건물과 자전거, 우측에는 가로수/전신주/울타리가 보임. 화면 텍스트: `한문철TV`.

## QA 실측

질문 1:

- Query: `영상에서 차량 바로 앞에 사람이 가까이 접근한 시점과 상황을 설명해줘.`
- Demo answer: `영상의 [9초] 지점에서 차량 앞 유리 바로 앞에 사람이 가까이 접근하여 차량 보닛 앞쪽에 몸을 숙이고 서 있는 모습이 확인됩니다.`
- Similarity: `0.4298`

질문 2:

- Query: `차량 앞 사람은 어떤 자세였고, 주변 도로에는 무엇이 보였나요?`
- Demo answer: `차량 앞 사람은 몸을 숙인 자세에 있으며, 차량 앞 유리 바로 앞에 가까이 다가와 있습니다. 주변 도로에는 승용차 몇 대가 보이고, 좌측에는 건물과 자전거들이, 우측에는 가로수와 전신주, 울타리가 보입니다.`
- Similarity: `0.5405`

질문 3:

- Query: `영상 화면에서 확인되는 텍스트나 표지는 무엇인가요?`
- Demo answer: `영상 화면에서 확인되는 텍스트나 표지는 "한문철TV"와 "정직한포차", 그리고 남성 사진과 제목 그래픽이 포함되어 있습니다.`
- Similarity: `0.2392`

주의: 원본 `/qa` 응답에는 `<thinking>` 블록이 포함된다. demo에는 위처럼 후처리해 노출 답변만 사용한다.

## 평가 결과

`/media/30fa5dfc-9298-4af3-be55-2ad8e197a8ed/evaluate`에 위 3문항을 전달해 측정.

| Metric | Value |
| --- | ---: |
| answer_relevance | 1.00 |
| groundedness | 1.00 |
| retrieval_precision | 0.00 |
| visual_text_alignment | 0.00 |
| wer | null |
| cer | null |

## 해석

- AR/GR 1.00: QA 답변은 질문과 직접 관련 있고, context 안의 `[9초]` visual evidence에 잘 grounding됨.
- RP 0.00: `calculate_retrieval_precision()`이 `seg.text`만 judge에 전달하고 `frame_description`을 무시한다. 이 CCTV run의 실제 근거는 visual frame description에 있으므로, text-only RP는 visual-only QA를 실패로 판정한다.
- Visual-text alignment 0.00: 음성 전사와 화면 설명이 같은 장면을 설명하지 않는다. CCTV/블랙박스 실험에서는 정상적인 metric mismatch로 보는 편이 맞다.

## Demo 반영 원칙

- 기존 `0.38 -> 0.84` 같은 더미 before/after 수치는 제거한다.
- 현재 카드에는 단일 실제 run의 관측값과 평가기 한계를 함께 적는다.
- baseline v5-code는 문서상 실패 모드로만 남기고, 측정된 숫자처럼 쓰지 않는다.
