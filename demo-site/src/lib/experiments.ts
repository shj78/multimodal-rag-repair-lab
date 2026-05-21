export type TimelineStep = {
  label: string;
  change: string;
  outcome: string;
  status: "fail" | "progress" | "success";
};

export type ModelChoice = {
  role: string;
  model: string;
  reason: string;
};

export type Improvement = {
  label: string;
  before: string;
  after: string;
};

export type Experiment = {
  slug: string;
  shortLabel: string;
  title: string;
  kicker: string;
  oneLiner: string;
  cardSummary: string;
  dataset: string;
  duration: string;
  artifact: string;
  question: string;
  cardStats: { label: string; value: string }[];
  problemStatement: string[];
  firstAttempt: {
    answer: string;
    note: string;
  };
  failureAnalysis: string[];
  timeline: TimelineStep[];
  finalAnswer: {
    sectionTitle?: string;
    eyebrow?: string;
    tone?: "success" | "progress";
    answer: string;
    summary: string;
    improvements: Improvement[];
  };
  media?: {
    type: "video";
    src: string;
    title: string;
    note: string;
  };
  modelChoices: ModelChoice[];
  techBadges: string[];
  comparison: {
    columns: string[];
    rows: string[][];
  };
  learnings: string[];
  architecture: string[];
  teamNote: string;
  snapshot: Record<string, unknown>;
  art: {
    variant: "cat" | "code" | "cctv" | "movie";
    base: string;
    accent: string;
    glow: string;
    headline: string;
    eyebrow: string;
    tag: string;
  };
};

export const experiments: Experiment[] = [
  {
    slug: "print",
    shortLabel: "01",
    title: "print() Multimodal Parse",
    kicker: "화면과 음성이 다를 때 무엇을 믿어야 하는가",
    oneLiner: "화면에는 `print()`가 있었지만 QA는 끝내 빠뜨렸다. 이 실험은 그 누락이 음성 전사, 전사 교정, 화면 인식 중 어느 단계에서 생기는지 좁혀간 기록이다.",
    cardSummary:
      "3분 13초 파이썬 강의 영상에서 `print()`가 계속 누락됐다. Whisper prompt, vision-guided correction, gpt-5.4 OCR 업그레이드를 순차 실험하며 실패 원인을 오디오에서 비전, 다시 QA 열거 안정성으로 좁혔다.",
    dataset: "coding-tutorial / 5 eval questions",
    duration: "03:13",
    artifact: "ASR + frame analyses + eval runs",
    question: "영상에서 사용된 파이썬 내장 함수를 모두 나열해줘.",
    cardStats: [
      { label: "T1 answer", value: "4/5 → 5/5" },
      { label: "print(", value: "4/10 → 10/10" },
      { label: "GR/RP", value: "0.82/0.40 → 0.94/0.53" },
    ],
    problemStatement: [
      "데이터셋은 3분 13초짜리 파이썬 평균 계산기 강의이고, 평가 질문 5개 중 T1은 영상에 등장한 내장 함수 `print`, `input`, `split`, `int`, `len`을 모두 열거해야 했다.",
      "Baseline QA는 `input`, `split`, `int`, `len`만 답하고 `print`를 빠뜨렸다. 화면에는 `print()`가 있었지만, 화자가 한국어로 ‘프린트’라고 말한 탓에 전사 텍스트와 코드 토큰 사이 표현이 어긋났다.",
      "이 실험의 핵심은 단순한 모델 업그레이드가 아니었다. `print()`가 빠진 원인을 음성 전사 ASR, 화면 코드 인식 vision OCR, 전사 교정, 최종 QA 응답 생성 단계로 나누어 추적하는 데 있었다.",
    ],
    firstAttempt: {
      answer: "input, split, int, len",
      note: "정답 5개 중 4개만 복원했다. `print()`는 화면에는 있었지만 검색 context에 안정적으로 들어오지 않아 QA가 근거로 사용할 수 없었다.",
    },
    failureAnalysis: [
      "Whisper가 음성을 잘못 들은 것은 아니었다. 화자는 `print()`를 한국어로 “프린트”라고 말했고, Whisper는 이를 그대로 전사했다. 문제는 전사 정확도가 아니라, 검색과 QA에 필요한 코드 표기 `print()`가 텍스트에 남지 않았다는 점이었다.",
      "Correction v1은 화면에 보이는 코드 정보를 이용해 Whisper 전사를 고치려는 시도였다. 하지만 모델이 필요한 단어만 바꾸지 않고, 화면의 코드 블록과 설명을 전사에 길게 덧붙이면서 원문보다 과도하게 긴 결과를 만들었다. 이를 막기 위해 “교정 결과가 원문 길이의 1.3배를 넘으면 폐기”하는 guard 규칙을 두었고, 5개 결과가 이 규칙에 걸려 버려졌다. 검색 근거의 관련도를 보는 RP는 일부 개선됐지만, 답변 관련도 AR과 근거 충실도 GR은 함께 떨어져 안정적인 해결책으로 보기 어려웠다.",
      "Correction v2는 단어 수준 치환만 허용해 guard reject를 0건으로 줄였고 전체 GR/RP 최고 조합을 만들었다. 하지만 핵심 T1에서는 여전히 `print()`가 빠져, 오디오/교정 레이어만으로는 해결할 수 없었다.",
      "gpt-5.4 vision으로 바꾸자 프레임 설명 10개 모두에 `print(`가 기록됐다. 모델을 올려서 결과가 좋아진 것은 맞다. 다만 좋아진 지점은 QA 모델이 정답을 더 잘 추측한 것이 아니라, QA가 검색해서 읽을 수 있는 텍스트 근거에 `print()`가 더 자주 들어간 것이다. 이전에는 화면에 보이는 `print()`가 검색 근거에 충분히 남지 않았다. 그래서 화면 분석 단계가 `print()`를 글로 더 잘 남길수록 QA가 그것을 정답 근거로 발견할 가능성이 커졌다.",
      "마지막으로 남은 문제는 답변 생성 단계의 비결정성이었다. gpt-5.4 vision 조건의 첫 실행에서는 검색 근거 안에 5개 함수가 모두 있었는데도 QA가 `print`, `split` 2개만 답했다. 같은 조건으로 다시 실행한 두 번째 결과에서야 `print`, `input`, `split`, `int`, `len`을 모두 나열했다. 즉 화면 인식은 개선됐지만, 생성 모델 특성상 같은 근거를 보고도 답변 항목 수가 달라지는 변동성이 남아 있었다.",
    ],
    timeline: [
      {
        label: "TEAM Delta-03",
        change: "correction OFF baseline",
        outcome: "전체 AR 0.94, GR 0.82, RP 0.40. T1은 4개 함수만 답했고 `print()`는 끝까지 누락됐다.",
        status: "fail",
      },
      {
        label: "Correction v1",
        change: "vision-guided transcription correction",
        outcome: "RP는 0.53으로 올랐지만 AR 0.86, GR 0.72로 하락했다. 코드 블록 삽입형 과교정과 guard reject 5건이 새 실패 모드였다.",
        status: "progress",
      },
      {
        label: "Correction v2",
        change: "단어 수준 치환 + 길이 guard",
        outcome: "guard reject를 0건으로 줄이고 GR을 회복했지만, T1 답변은 여전히 `input`, `split` 중심으로 축소됐다.",
        status: "progress",
      },
      {
        label: "Whisper prompt",
        change: "Python 어휘 hint + correction v2",
        outcome: "최고 조합은 GR 0.94, RP 0.53까지 올랐다. 다만 ‘프린트’ 발화는 여전히 `print`로 바뀌지 않아 핵심 누락은 남았다.",
        status: "progress",
      },
      {
        label: "Vision Prompt",
        change: "vision gpt-4o-mini → gpt-5.4",
        outcome: "프레임 설명량이 2.1배 늘고 `print(` 등장 프레임이 4/10에서 10/10으로 증가했다. Run 2에서 5개 함수 전체를 복원했다.",
        status: "success",
      },
    ],
    finalAnswer: {
      answer: "print, input, split, int, len",
      summary:
        "최종 해결은 한 번의 프롬프트 변경이 아니라 병목 이동이었다. 전사 교정은 전체 근거 충실도와 검색 관련도를 개선했지만 `print()` 누락은 해결하지 못했다. gpt-5.4 vision은 화면 속 `print()`를 프레임 설명에서 더 자주 포착했다.",
      improvements: [
        { label: "T1 answer", before: "4/5 functions", after: "5/5 functions" },
        { label: "Best GR/RP", before: "0.82 / 0.40", after: "0.94 / 0.53" },
        { label: "`print(` frame hits", before: "4/10", after: "10/10" },
      ],
    },
    media: {
      type: "video",
      src: "/media/print-sample.mp4",
      title: "Python average calculator lecture",
      note: "`print()`, `input()`, `split()`, `int()`, `len()`이 등장하는 3분 13초 샘플 영상입니다.",
    },
    modelChoices: [
      {
        role: "ASR",
        model: "Whisper-1",
        reason: "전사 품질과 타임스탬프는 안정적이었다. 동시에 ‘정확한 전사’가 검색 가능한 코드 토큰을 보장하지 않는다는 실패를 드러냈다.",
      },
      {
        role: "Vision",
        model: "gpt-5.4",
        reason: "gpt-4o-mini보다 프레임 설명이 2.1배 길어졌고 `print(` 포착률이 4/10에서 10/10으로 올랐다. 음성 전사에는 없던 `print()` 표기가 화면 설명 텍스트에 들어가면서, QA가 검색할 수 있는 근거가 늘었다.",
      },
      {
        role: "Correction",
        model: "GPT-4o-mini",
        reason: "v2 prompt와 결합했을 때 원문 길이 폭주 없이 단어 치환을 수행했고, guard reject를 5건에서 0건으로 줄였다.",
      },
      {
        role: "Embedding",
        model: "text-embedding-3-small",
        reason: "현재 데모 환경에서는 OpenAI embedding으로 통일해 전사, 비전, QA, 평가 흐름을 같은 API 설정에서 재현할 수 있게 했다.",
      },
    ],
    techBadges: [
      "Whisper-1",
      "Whisper Prompt",
      "Vision-guided Correction",
      "Correction Guard",
      "GPT-4o-mini",
      "gpt-5.4",
      "text-embedding-3-small",
      "Frame OCR",
    ],
    comparison: {
      columns: ["실험", "검증 가설", "T1 결과", "전체 지표", "판정"],
      rows: [
        ["TEAM Delta-03", "correction 없이 기준선 확인", "4/5, print 누락", "AR 0.94 / GR 0.82 / RP 0.40", "실패"],
        ["Correction v1", "vision으로 전사 교정", "2/5로 후퇴", "AR 0.88 / GR 0.80 / RP 0.53", "부분 개선"],
        ["Correction v2", "과교정 guard 안정화", "2/5 유지", "AR 0.88 / GR 0.82 / RP 0.40", "부분 개선"],
        ["Whisper+v2", "ASR hint와 correction 조합", "2/5 유지", "AR 0.88 / GR 0.94 / RP 0.53", "전체 지표 개선"],
        ["gpt-5.4 Run 1", "화면 설명에 print 포함", "2/5, print 포함", "AR 0.88 / GR 0.92 / RP 0.33", "분산 확인"],
        ["gpt-5.4 Run 2", "동일 조건 반복", "5/5 복원", "AR 0.88 / GR 0.78 / RP 0.47", "성공"],
      ],
    },
    learnings: [
      "오디오 전사를 그대로 믿으면 코드 표기처럼 화면에만 명확히 보이는 단서를 놓칠 수 있다. ‘프린트’ 발화와 `print()` 함수 표기를 구분하려면 화면 분석 같은 추가 확인이 필요했다.",
      "전체 지표가 좋아져도 핵심 질문이 해결됐다고 볼 수는 없었다. Correction v2는 GR/RP를 올렸지만, 정작 `print()` 누락은 그대로 남아 있어서 질문별 실패 여부를 따로 확인해야 했다.",
      "같은 근거를 줘도 LLM 답변은 실행마다 달라질 수 있었다. 단일 실행 결과만 보고 성공과 실패를 단정하지 않으려면, 반복 실행과 고정된 답변 형식으로 비결정성을 다뤄야 한다는 점을 배웠다.",
    ],
    architecture: [
      "Whisper transcript (음성 전사)",
      "Frame vision analysis (화면 코드 인식)",
      "Optional vision-guided correction (화면 기반 전사 교정)",
      "Chunk embedding (검색용 벡터화)",
      "Retrieval + optional rerank (후보 검색과 선택적 재정렬)",
      "Grounded QA (근거 기반 답변 생성)",
    ],
    teamNote:
      "이 케이스는 ‘정확한 ASR → 좋은 RAG’라는 단순 가정을 깨는 대표 사례로 둔다. 수치는 delta-03 print 실험 흐름으로 통일했고, 성공과 남은 한계를 함께 보여준다.",
    snapshot: {
      dataset: "coding-tutorial",
      duration: "3m13s",
      questionCount: 5,
      criticalQuestion: "영상에서 사용된 파이썬 내장 함수를 모두 나열해줘",
      goldFunctions: ["print", "input", "split", "int", "len"],
      experimentDesign: {
        delta03Correction: "ASR prompt and correction variants, 5 QA questions",
        delta03Vision: "vision model upgrade gpt-4o-mini to gpt-5.4, two fresh runs",
      },
      keyFindings: {
        asrPrompt: "No effect on clear Korean phonetic utterance '프린트'",
        correctionV1: "RP improved but guard rejected 5 over-expanded corrections",
        correctionV2: "Best aggregate GR/RP with 0 guard rejects, but T1 still failed",
        visionUpgrade: "gpt-5.4 supplied print( in 10/10 frame analyses",
        remainingBottleneck: "QA enumeration variance and judge sensitivity",
      },
      metricTrajectory: {
        baselineCorrectionOff: { ar: 0.94, gr: 0.82, rp: 0.4, t1: "input, split, int, len" },
        whisperPromptCorrectionV2: { ar: 0.88, gr: 0.94, rp: 0.53, t1: "input, split" },
        visionGpt54Run1: { ar: 0.88, gr: 0.92, rp: 0.33, t1: "print, split" },
        visionGpt54Run2: { ar: 0.88, gr: 0.78, rp: 0.47, t1: "print, input, split, int, len" },
      },
      visionFrameAnalysis: {
        gpt4oMiniTotalChars: 4705,
        gpt54TotalChars: 9872,
        printHits: "4/10 -> 10/10",
      },
      sources: [
        "delta-03 print experiment notes",
        "delta-03 vision upgrade run notes",
      ],
    },
    art: {
      variant: "code",
      base: "#07111f",
      accent: "#2563eb",
      glow: "#67e8f9",
      headline: "print()",
      eyebrow: "Vision-guided correction",
      tag: "Multimodal",
    },
  },
  {
    slug: "cctv",
    shortLabel: "02",
    title: "CCTV Scene Prompt Shift",
    kicker: "현실 영상에 RAG를 붙이면 어디서부터 무너지는가",
    oneLiner: "실제 블랙박스 영상을 v6-scene으로 다시 ingest해, 화면 근거가 QA까지 전달되는지 검증했다.",
    cardSummary:
      "도메인 중립 프롬프트는 4초와 9초 장면을 구조화했지만, 평가기는 아직 frame_description이 아니라 음성 전사 텍스트만 보고 retrieval precision을 계산했다.",
    dataset: "Han Moon-cheol dashcam / 1 visual chunk",
    duration: "00:15",
    artifact: "v6-scene frame_desc + QA/eval trace",
    question: "영상에서 차량 바로 앞에 사람이 가까이 접근한 시점과 상황을 설명해줘.",
    cardStats: [
      { label: "Vision timestamps", value: "4s / 9s" },
      { label: "QA judge", value: "AR 1.00 / GR 1.00" },
      { label: "RP caveat", value: "0.00 text-only" },
    ],
    problemStatement: [
      "AI가 실제 업무에서 효과적으로 쓰일 수 있는 사례를 찾던 중, 해외 법률 사무소들이 사건 검토 과정에서 많은 양의 이미지와 영상을 분석하는 데 AI를 활용하고 있다는 기사를 확인했다. 이 케이스는 그 아이디어에서 출발했다.",
      "사고 영상 분석도 AI로 어디까지 가능할지 확인해보고 싶었다. 블랙박스나 CCTV 영상이 많아질수록 사람이 모든 영상을 일일이 돌려보며 장면을 찾는 방식은 비효율적이고, 필요한 장면을 검색해 답변하는 RAG 방식이 더 적합할 수 있다고 봤다.",
      "사고 영상은 음성보다 화면 단서가 핵심이기 때문에, 인물, 차량, 접근 시점, 이상 행동 같은 장면 정보를 구조적으로 뽑아낼 수 있는 프롬프트가 필요했다.",
    ],
    firstAttempt: {
      answer: "코드 영역이나 실행 결과는 확인되지 않습니다.",
      note: "틀린 답은 아니지만 CCTV 질문에는 아무 도움도 주지 못하는 완전한 도메인 미스매치였다.",
    },
    failureAnalysis: [
      "이 영상에서 답을 찾는 데 중요한 정보는 음성이 아니라 화면이었다. 전사에는 ‘아 알겠습니다’ 같은 짧은 말만 남아 있었고, 실제 단서는 프레임 설명에 있었다.",
      "답변 생성에는 프레임 설명이 사용됐기 때문에 9초 장면을 설명할 수 있었다. 하지만 RP 점수를 계산하는 평가기는 전사 텍스트만 확인하고 프레임 설명은 보지 못했다. 그래서 실제 답변은 장면을 설명했지만, RP는 관련 근거를 찾지 못한 것처럼 0.00으로 나왔다.",
    ],
    timeline: [
      {
        label: "Frame sampling",
        change: "3 fpm → 10 fpm",
        outcome: "짧은 사고 장면을 놓치지 않도록 화면 캡처 간격을 촘촘하게 조정했다.",
        status: "progress",
      },
      {
        label: "Measured ingest",
        change: "v6-scene 장면 분석",
        outcome: "14.84초 영상에서 4초 도로 장면과 9초 보닛 앞 인물 접근 장면을 프레임 설명으로 저장했다.",
        status: "progress",
      },
      {
        label: "QA check",
        change: "사고 장면 질문",
        outcome: "차량 앞에 사람이 가까이 접근한 시점과 상황을 묻자, QA가 9초 장면을 근거로 답변했다.",
        status: "progress",
      },
      {
        label: "Evaluate",
        change: "AR/GR/RP 측정",
        outcome: "AR 1.00, GR 1.00으로 답변 품질은 통과했다. RP 0.00은 평가기가 프레임 설명을 보지 못한 한계로 남았다.",
        status: "success",
      },
    ],
    finalAnswer: {
      answer:
        "영상의 [9초] 지점에서 차량 앞 유리 바로 앞에 사람이 가까이 접근해 차량 보닛 앞쪽에 몸을 숙이고 서 있는 모습이 확인됩니다.",
      summary:
        "프레임 설명에 4초 도로 장면과 9초 인물 접근 장면이 남았고, QA는 그 장면을 근거로 사고 상황을 설명할 수 있었다.",
      improvements: [
        { label: "Frame capture", before: "3 fpm", after: "10 fpm" },
        { label: "Scene evidence", before: "누락 가능", after: "4s / 9s 장면 저장" },
        { label: "QA result", before: "장면 특정 어려움", after: "9초 접근 장면 설명" },
      ],
    },
    media: {
      type: "video",
      src: "/media/cctv-sample.mp4",
      title: "Han Moon-cheol dashcam clip",
      note: "v6-scene 프롬프트로 4초와 9초 장면을 분석한 15초 블랙박스 클립입니다.",
    },
    modelChoices: [
      {
        role: "Vision",
        model: "GPT-4o (v6-scene prompt)",
        reason: "4초와 9초 장면을 `[장면][인물/사물][이벤트][텍스트]` 구조로 저장해 visual QA의 핵심 근거를 만들었다.",
      },
      {
        role: "ASR",
        model: "Whisper-1",
        reason: "실제 run에는 포함됐지만, 이 클립에서는 음성 전사가 장면 질문의 주 근거가 아니었다.",
      },
      {
        role: "Embedding",
        model: "text-embedding-3-small",
        reason: "현재 공개 준비용 Supabase run의 실제 설정과 차원을 그대로 반영했다.",
      },
      {
        role: "QA",
        model: "GPT-4o-mini",
        reason: "HyDE, hybrid search, LLM rerank 뒤의 accepted visual chunk를 바탕으로 grounded answer를 생성했다.",
      },
    ],
    techBadges: [
      "v6-scene Prompt",
      "GPT-4o Vision",
      "Timestamped Context",
      "Semantic Chunking",
      "Hybrid + HyDE",
      "LLM Rerank",
    ],
    comparison: {
      columns: ["항목", "실측값", "근거", "메모"],
      rows: [
        ["Ingest", "ready / 1 chunk", "media 30fa5dfc", "14.84초 블랙박스 클립"],
        ["Vision context", "4s, 9s", "frame_description", "9초 보닛 앞 인물 이벤트 포착"],
        ["QA judge", "AR 1.00 / GR 1.00", "/evaluate n=3", "답변은 visual context에 grounded"],
      ],
    },
    learnings: [
      "사고 영상 QA에서는 전사보다 화면 단서가 더 중요한 근거가 될 수 있다. 그래서 장면 설명과 타임스탬프를 함께 남겨야 검색과 답변에 사용할 수 있었다.",
      "답변은 화면 근거를 잘 사용했지만, 기존 평가는 주로 전사 텍스트를 기준으로 판단해 RP가 낮게 나왔다. 평가 방식도 영상 근거를 읽을 수 있게 바뀌어야 한다는 점을 배웠다.",
      "Vision 프롬프트는 모델 성능만큼이나 도메인에 맞는 구조가 중요했다. 사고 영상에서는 코드나 자막보다 인물, 차량, 움직임, 시점 같은 항목을 먼저 뽑아야 했다.",
    ],
    architecture: [
      "Upload (영상 업로드)",
      "Whisper-1 transcript (음성 전사)",
      "GPT-4o v6-scene frames (장면 프레임 분석)",
      "Semantic chunk (의미 단위 청킹)",
      "Hybrid/HyDE/LLM rerank (검색 후보 보강)",
      "Grounded QA (근거 기반 답변 생성)",
    ],
    teamNote:
      "이 케이스는 블랙박스 영상에서 장면 단서를 QA 근거로 전달할 수 있는지 확인한 기록이다. 4월 실험에서도 차량 앞 인물 접근 장면은 포착됐고, 데모에서는 그 흐름을 짧은 클립과 평가 지표로 정리했다.",
    snapshot: {
      mediaId: "30fa5dfc-9298-4af3-be55-2ad8e197a8ed",
      filename: "한문철_무단횡단.mp4",
      durationSeconds: 14.84,
      segmentCount: 1,
      visionPromptVersion: "v6-scene",
      visionTimestamps: ["4s", "9s"],
      qaQuestions: [
        "영상에서 차량 바로 앞에 사람이 가까이 접근한 시점과 상황을 설명해줘.",
        "차량 앞 사람은 어떤 자세였고, 주변 도로에는 무엇이 보였나요?",
        "영상 화면에서 확인되는 텍스트나 표지는 무엇인가요?",
      ],
      metrics: {
        answerRelevance: 1.0,
        groundedness: 1.0,
        retrievalPrecision: 0.0,
        visualTextAlignment: 0.0,
      },
      caveats: [
        "retrieval_precision currently judges seg.text only, not frame_description",
      ],
      sources: [
        "docs/notes/cctv-demo-measurements-2026-05-13.md",
        "docs/track-b/pr-delta-03.md",
      ],
    },
    art: {
      variant: "cctv",
      base: "#110b0b",
      accent: "#7f1d1d",
      glow: "#fb923c",
      headline: "EVENT",
      eyebrow: "Prompt shift",
      tag: "Real-world",
    },
  },
  {
    slug: "movie",
    shortLabel: "03",
    title: "Speaker-Aware Movie Debate",
    kicker: "세 명이 말할 때 retrieval은 누구의 발화인지 알아야 한다",
    oneLiner: "39분 영화 토론에서 ‘누가 그 말을 했는지’를 답하기 위해, 각 대사 구간에 발화자 메타데이터를 붙이고 QA가 그 정보를 함께 읽도록 만든 실험이다.",
    cardSummary:
      "같은 영화 제목이 여러 번 반복되는 토론에서는 텍스트만으로 발화자를 구분하기 어렵다. 영상 대사를 짧은 구간으로 나누고, 각 구간에 화자 이름을 붙여 검색 결과와 최종 답변 근거에 함께 보이도록 연결했다.",
    dataset: "cinephile-worldcup / 39 min",
    duration: "39:00",
    artifact: "speaker_id schema + annotation CLI",
    question: "결승전을 두고 ‘맥빠지는 느낌’이라고 말한 사람은 누구이고, 어떤 맥락이었나요?",
    cardStats: [
      { label: "Pipeline", value: "6/7 완료" },
      { label: "Speaker data", value: "segment + media" },
      { label: "Answer", value: "허키 복원" },
    ],
    problemStatement: [
      "세 명의 화자가 겹치는 영화 토론 영상에서는 같은 영화 제목이 여러 구간에 흩어져 등장해, 대사 텍스트만 검색해서는 정답 구간을 다시 집기 어렵다.",
      "질문셋은 ‘누가’와 ‘어떤 어조로’가 핵심이라, 검색된 대사 구간과 최종 답변 근거에 화자 이름이 함께 남아야 한다.",
    ],
    firstAttempt: {
      answer: "김간지가 결승전이 지루하다고 말했다고 보입니다.",
      note: "화자 정보가 없는 상태에서는 같은 영화 이야기가 여러 구간에 반복되어, 누가 한 말인지 잘못 짚을 수 있다.",
    },
    failureAnalysis: [
      "기존 검색 결과는 대사 내용만 보여주고, 그 말을 누가 했는지는 함께 보여주지 않았다.",
      "처음에는 검색된 대사 구간에 화자 이름이 붙어 있지 않았다. 그래서 같은 영화 이야기가 여러 번 나오면, 답변이 다른 사람의 발화를 정답처럼 가져올 수 있었다.",
      "수정 후에는 검색 결과와 답변 근거에 화자 이름을 함께 붙였다. 그 결과 ‘맥빠지는 느낌’이라는 발화를 허키의 말로 연결할 수 있었다.",
    ],
    timeline: [
      {
        label: "Baseline issue",
        change: "speaker metadata missing",
        outcome: "화자 특정 질문에서 발화자를 잘못 짚는 문제가 확인됨",
        status: "fail",
      },
      {
        label: "ALTER Schema",
        change: "media_segments.speaker_id",
        outcome: "청크 레벨 화자 컬럼과 media_files.metadata.speakers 저장 구조 추가",
        status: "progress",
      },
      {
        label: "Annotation CLI",
        change: "GPT speaker labeling",
        outcome: "각 대사 구간을 김간지·김민경·허키 중 한 명의 발화로 라벨링하고 저장",
        status: "progress",
      },
      {
        label: "QA integration",
        change: "HyDE + LLM rerank + answer context",
        outcome: "화자 메타데이터를 HyDE와 LLM rerank 프롬프트에 전달하고, 최종 답변 근거에도 `(화자)`를 붙여 허키 발화로 복원",
        status: "success",
      },
    ],
    finalAnswer: {
      sectionTitle: "최종 답변",
      eyebrow: "Resolved answer",
      tone: "success",
      answer:
        "허키가 결승전을 두고 ‘조금 맥빠지는 느낌’이라고 말했다. 결승 대진의 긴장감이 기대보다 약하다는 맥락에서 나온 발화였다.",
      summary:
        "초기 답변은 김간지로 잘못 짚었지만, 검색된 대사 구간에 화자 이름을 붙이면서 ‘누가 말했는가’를 허키로 바로잡았다.",
      improvements: [
        { label: "Attribution", before: "김간지", after: "허키" },
        { label: "Evidence", before: "화자 이름 없음", after: "화자 포함" },
        { label: "Question", before: "발화자 혼동", after: "정답 복원" },
      ],
    },
    media: {
      type: "video",
      src: "/media/movie-speaker-full.mp4",
      title: "Cinephile worldcup full debate",
      note: "화자 메타데이터 검증에 사용한 39분 원본 영상입니다. 파일이 316MB라 첫 로딩이 느릴 수 있습니다.",
    },
    modelChoices: [
      {
        role: "Speaker labeling",
        model: "GPT-4o",
        reason: "39분 분량의 대사를 한 번에 검토해 김간지·김민경·허키 중 누가 말했는지 붙이는 오프라인 작업이다. 비용보다 긴 문맥과 말투, 응답 흐름을 구분하는 품질이 더 중요해 GPT-4o를 썼다.",
      },
      {
        role: "Candidate ranking",
        model: "GPT-4o-mini",
        reason: "검색이 가져온 여러 대사 구간을 한 번에 비교해 질문과 가장 가까운 순서로 다시 정렬했다. 후보가 짧기 때문에 GPT-4o-mini로도 충분했고, 속도와 비용을 낮출 수 있었다.",
      },
      {
        role: "Embedding strategy",
        model: "기존 embedding 유지",
        reason: "실패 원인은 임베딩 모델이 아니라 ‘누가 말했는가’ 정보가 검색 결과에서 사라진 것이었다. 그래서 벡터를 다시 만들기보다 발화자 정보를 별도 메타데이터로 붙였다.",
      },
    ],
    techBadges: [
      "speaker_id Column",
      "Metadata Backfill",
      "v2-speaker HyDE",
      "v2-speaker Rerank",
      "Context Prefix",
      "No Re-embedding",
    ],
    comparison: {
      columns: ["Phase", "상태", "근거", "메모"],
      rows: [
        ["ALTER Schema", "완료", "001_add_speaker_id.sql", "media_segments.speaker_id 추가"],
        ["Labeling CLI", "완료", "annotate_speakers.py", "대사 구간별 화자 라벨 저장"],
        ["QA path", "완료", "HyDE + LLM rerank + chat", "`(화자)` context와 speaker_intro 연결"],
        ["Core question", "해결", "39분 원본", "허키 발화로 정정"],
      ],
    },
    learnings: [
      "토론 영상에서는 텍스트 본문만으로는 ‘누가 말했는가’를 안정적으로 보존하기 어렵다.",
      "발화자 정보를 메타데이터로 저장해두면, 답변 단계에서 ‘누가 말했는가’를 더 정확히 판단할 수 있다.",
      "정량 지표는 별도 검증 대상으로 분리하고, 이 페이지에서는 핵심 질문에서 잘못 짚은 발화자를 바로잡은 흐름만 다룬다.",
    ],
    architecture: [
      "Existing chunks (기존 청크 활용)",
      "GPT speaker labeling (화자 라벨링)",
      "speaker_id column (청크별 화자 컬럼)",
      "media speakers metadata (영상 단위 화자 정보)",
      "HyDE/rerank speaker_intro (화자 정보 검색 반영)",
      "Grounded QA context (화자 포함 답변 근거)",
    ],
    teamNote:
      "이 페이지는 39분 토론에서 화자 이름을 잃지 않도록 검색 파이프라인을 바꾼 기록이다. 직접 만든 질문셋에는 영화 포스터 인식, 긴 논의 구간 검색, 화자·어조 구분 문제가 함께 들어 있었고, 여기서는 마지막으로 풀린 36분대 ‘맥빠지는 느낌’ 발언자 구분 사례를 정리했다.",
    snapshot: {
      dataset: "cinephile-worldcup_21-60min",
      questionTrack: "화자/어조 메타데이터 검증",
      goldHint: "36:00~, 허키가 '결승전이 조금 맥빠지는 느낌'",
      implementationStatus: {
        schema: "done",
        annotationCli: "done",
        updateSegmentSpeaker: "done",
        contextTextSpeakerPrefix: "done",
        hydePromptV2Speaker: "done",
        llmRerankPromptV2Speaker: "done",
        coreQuestionAnswer: "resolved",
        pitchEmotionMetrics: "not measured",
      },
      sources: [
        "notes/03_영화-월드컵-실험-질문셋.md",
        "experiments/track4-speaker-annotation/README.md",
        "docs/track-b/pr-delta-03.md",
      ],
    },
    art: {
      variant: "movie",
      base: "#0a1013",
      accent: "#14532d",
      glow: "#f87171",
      headline: "3 speakers",
      eyebrow: "Metadata retrieval",
      tag: "Debate",
    },
  },
];

export const experimentMap = new Map(
  experiments.map((experiment) => [experiment.slug, experiment]),
);

export function getExperiment(slug: string) {
  return experimentMap.get(slug);
}
