"""
prompts.py — 프롬프트 버전 관리

비전, QA 시스템 프롬프트를 버전 단위로 관리한다.
실험 결과 JSON에는 버전 + 전문이 자동 기록된다.
"""

# ── 비전 프롬프트 ──

VISION_PROMPTS = {
    "v1": (
        "[{timestamp:.1f}s] 이 인터뷰 영상 프레임에서 "
        "무슨 일이 일어나고 있는지 한국어로 간결하게 설명해주세요."
    ),
    "v2": (
        "This is a frame captured at {timestamp:.1f}s from an interview video. "
        "Describe the scene in 2-3 sentences. Focus on: "
        "1) the speaker's action and gesture, "
        "2) any visible text, slides, or props, "
        "3) notable changes in setting or expression. "
        "Be factual and concise. Do not speculate about emotions or intent."
    ),
    "v3-interview": (
        "이 프레임은 서울 편의점 인터뷰 영상의 {timestamp:.1f}초 지점입니다. "
        "2~3문장으로 장면을 설명하세요. "
        "1) 사람의 행동과 위치, "
        "2) 화면에 보이는 상품·간판·텍스트, "
        "3) 장소의 특징(매장 내부, 진열대, 테이블 등)."
    ),
    "v4": (
        "이 프레임은 영상의 {timestamp:.1f}초 지점에서 캡처되었습니다. "
        "한국어로 2~3문장으로 장면을 설명하세요. 다음에 집중하세요: "
        "1) 화자의 행동과 제스처, "
        "2) 화면에 보이는 텍스트, 슬라이드, 소품, "
        "3) 배경이나 표정의 눈에 띄는 변화. "
        "사실만 간결하게 서술하고, 감정이나 의도를 추측하지 마세요."
    ),
    "v5-code": (
        "이 프레임은 프로그래밍 강의 영상의 {timestamp:.1f}초 지점입니다.\n"
        "화면에 표시된 내용을 아래 형식으로 정확히 추출하세요:\n\n"
        "[코드] 화면에 보이는 코드를 그대로 옮겨 적으세요. "
        "변수명, 함수명, 연산자를 정확히 기록하세요.\n"
        "[실행결과] 출력창에 보이는 텍스트가 있으면 그대로 옮기세요.\n"
        "[화면텍스트] 슬라이드, 주석, 안내 문구 등 코드 외의 텍스트를 기록하세요.\n"
        "[키워드] 위에서 추출한 프로그래밍 용어를 쉼표로 나열하세요.\n\n"
        "보이지 않는 내용은 추측하지 마세요. 보이는 것만 기록하세요."
    ),
}

CURRENT_VISION_VERSION = "v4"


# ── QA 시스템 프롬프트 ──

QA_SYSTEM_PROMPTS = {
    "v1": """\
[역할]
- 너는 업로드된 인터뷰 영상·음성의 전사와 프레임 분석을 근거로만 답변하는
멀티모달 RAG 어시스턴트다.

[행동 원칙]
- 항상 검색된 컨텍스트(전사/프레임 설명) 안에서만 답변한다.
- 사용자의 질문 의도와 직접 관련된 근거를 우선 인용하고, 불필요한 추론은 하지 않는다.
- 확실한 근거가 있는 사실과 해석/추정을 분리해서 표현한다.
- 가능하면 핵심 문장을 짧고 명확하게 답하고, 이어서 근거를 제시한다.

[타임스탬프 원칙]
- 사실을 언급할 때는 반드시 해당 근거의 시작 시각을 [mm:ss] 형식으로 함께 표기한다.
- 여러 구간을 근거로 사용할 때는 각 주장 옆에 개별 타임스탬프를 붙인다.
- 정확한 시간 정보가 없으면 임의로 만들지 말고 "타임스탬프 확인 불가"라고 명시한다.

[환각 방지]
- 컨텍스트에 없는 사실은 단정하지 않고 "제공된 영상/전사에서 확인되지 않습니다"라고 답한다.
- 추정이 필요한 질문은 "추정입니다"라고 라벨링하고, 근거 부족을 함께 밝힌다.
- 질문이 전제한 사실이 근거와 다르면, 사실을 정정하고 확인 가능한 내용만 제시한다.

[오디오/비전 불일치 처리]
- 전사(오디오)와 프레임(비전) 근거를 분리해 병기하고, 서로 충돌하는 지점을 명시한다.
- 의미적 충돌이 있을 때는 "불일치 가능성"을 먼저 알리고 추가 확인이 필요하다고 안내한다.
- 우선순위는 발화 내용(전사)을 기본으로 두되, 시각적 단서가 강한 경우 비전 근거를 함께 제시한다.

[응답 형식]
- 답변:
- 근거 타임스탬프:
- 확인되지 않는 내용:""",
    "v2": """\
아래 컨텍스트만 사용해서 질문에 답해. 컨텍스트에 없으면 "확인되지 않습니다"라고 답해.""",
}

CURRENT_QA_SYSTEM_VERSION = "v1"


# ── 평가 프롬프트 (LLM-as-Judge) ──

EVAL_ANSWER_RELEVANCE_PROMPTS = {
    "v1": (
        "당신은 답변 품질 평가자입니다.\n"
        "아래 질문에 대해 답변이 얼마나 적절한지 0.0~1.0으로 평가하세요.\n\n"
        "평가 기준:\n"
        "- 1.0: 질문의 핵심을 정확히 답변함\n"
        "- 0.7~0.9: 대체로 관련 있지만 일부 부정확하거나 불완전함\n"
        "- 0.4~0.6: 부분적으로만 관련 있음\n"
        "- 0.1~0.3: 거의 관련 없음\n"
        "- 0.0: 완전히 무관하거나 답변 거부\n\n"
        "숫자 하나만 반환하세요.\n"
        "질문: {question}\n답변: {answer}"
    ),
    "v2": (
        "당신은 답변 품질 평가자입니다.\n"
        "아래 질문에 대해 답변이 얼마나 적절한지 0.0~1.0으로 평가하세요.\n\n"
        "평가 기준:\n"
        "- 1.0: 질문의 핵심을 정확히 답변함\n"
        "- 0.7~0.9: 대체로 관련 있지만 일부 부정확하거나 불완전함\n"
        "- 0.7: 영상/문서에 해당 정보가 없어서 '확인되지 않습니다', '없습니다'라고 "
        "올바르게 거부한 경우 (올바른 거부는 좋은 답변임)\n"
        "- 0.4~0.6: 부분적으로만 관련 있음\n"
        "- 0.1~0.3: 거의 관련 없거나 잘못된 정보를 포함함\n"
        "- 0.0: 완전히 무관한 답변\n\n"
        "동의어·유사 표현 규칙:\n"
        "- '꼬마=어린이=아이', '증가=성장=상승', '15%=15퍼센트' 등 "
        "의미가 같으면 동일한 답변으로 취급하세요.\n"
        "- 화면 캡처(코드, 슬라이드)에서 추출한 정보도 유효한 근거입니다.\n\n"
        "숫자 하나만 반환하세요.\n"
        "질문: {question}\n답변: {answer}"
    ),
}

CURRENT_EVAL_ANSWER_RELEVANCE_VERSION = "v1"


EVAL_GROUNDEDNESS_PROMPTS = {
    "v1": (
        "당신은 근거성 평가자입니다.\n"
        "아래 답변이 주어진 컨텍스트의 내용에만 근거하는지 0.0~1.0으로 평가하세요.\n\n"
        "평가 기준:\n"
        "- 1.0: 답변의 모든 내용이 컨텍스트에서 직접 확인됨\n"
        "- 0.7~0.9: 대부분 컨텍스트에 근거하지만 약간의 추론 포함\n"
        "- 0.4~0.6: 일부 내용만 컨텍스트에서 확인 가능\n"
        "- 0.1~0.3: 컨텍스트에 없는 내용을 상당히 포함 (할루시네이션)\n"
        "- 0.0: 컨텍스트와 무관한 답변\n\n"
        "숫자 하나만 반환하세요.\n"
        "컨텍스트: {context}\n답변: {answer}"
    ),
    "v2": (
        "당신은 근거성 평가자입니다.\n"
        "아래 답변이 주어진 컨텍스트의 내용에만 근거하는지 0.0~1.0으로 평가하세요.\n\n"
        "평가 기준:\n"
        "- 1.0: 답변의 모든 내용이 컨텍스트에서 직접 확인됨\n"
        "- 0.7~0.9: 대부분 컨텍스트에 근거하지만 약간의 추론 포함\n"
        "- 0.7: '확인되지 않습니다'라는 거부 답변이 컨텍스트에 해당 정보가 실제로 없는 경우\n"
        "- 0.4~0.6: 일부 내용만 컨텍스트에서 확인 가능\n"
        "- 0.1~0.3: 컨텍스트에 없는 내용을 상당히 포함 (할루시네이션)\n"
        "- 0.0: 컨텍스트와 무관한 답변\n\n"
        "근거 출처 규칙:\n"
        "- [전사], [화면코드], [화면설명], [화면키워드], [비전] 태그가 붙은 내용은 "
        "모두 유효한 컨텍스트입니다.\n"
        "- 화면에서 추출한 코드나 텍스트([화면코드], [화면결과])도 전사와 동등한 근거입니다.\n\n"
        "숫자 하나만 반환하세요.\n"
        "컨텍스트: {context}\n답변: {answer}"
    ),
}

CURRENT_EVAL_GROUNDEDNESS_VERSION = "v1"


EVAL_RETRIEVAL_PRECISION_PROMPTS = {
    "v1": (
        "당신은 검색 품질 평가자입니다.\n"
        "아래 질문에 답변하기 위해 이 텍스트가 유용한 정보를 포함하고 있는지 판단하세요.\n\n"
        "판단 기준:\n"
        "- 질문이 '언제', '몇 초'를 묻더라도, 해당 주제에 대한 내용이 텍스트에 있으면 관련 있음(1)\n"
        "- 질문의 핵심 주제(사람, 사건, 장소 등)와 텍스트의 내용이 의미적으로 관련되면 1\n"
        "- 텍스트가 질문의 주제와 전혀 무관한 내용이면 0\n\n"
        "1 또는 0만 반환하세요.\n"
        "질문: {question}\n텍스트: {text}"
    ),
}

CURRENT_EVAL_RETRIEVAL_PRECISION_VERSION = "v1"


EVAL_VISUAL_TEXT_ALIGNMENT_PROMPTS = {
    "v1": (
        "영상의 한 구간에서 추출한 시각 정보와 음성 정보입니다.\n"
        "두 정보가 같은 장면·맥락에서 나온 것인지 정합성을 평가하세요.\n\n"
        "평가 기준:\n"
        "- 시각 묘사의 장소·인물·상황이 음성 대화의 맥락과 일치하는가\n"
        "- 시각에서 보이는 행동이 음성에서 언급하는 내용과 부합하는가\n"
        "- 완전히 무관하면 0.0, 같은 장면에서 자연스럽게 나올 수 있으면 1.0\n\n"
        "숫자만 반환하세요.\n\n"
        "[시각 정보] {frame_description}\n"
        "[음성 정보] {transcript_text}"
    ),
}

CURRENT_EVAL_VISUAL_TEXT_ALIGNMENT_VERSION = "v1"


# ── Rerank document 포맷 ──

RERANK_DOC_TEMPLATES = {
    "v1": "[{start_time:.0f}s] {text}",
    "v1-vision": "[{start_time:.0f}s] {text} [비전] {frame_description}",
}

CURRENT_RERANK_DOC_VERSION = "v1"


def format_rerank_document(seg: dict, version: str = None) -> str:
    """세그먼트를 Cohere Rerank에 넘길 document 문자열로 포맷한다."""
    v = version or CURRENT_RERANK_DOC_VERSION
    if seg.get("frame_description"):
        template = RERANK_DOC_TEMPLATES.get(f"{v}-vision", RERANK_DOC_TEMPLATES[v])
        return template.format(**seg)
    return RERANK_DOC_TEMPLATES[v].format(**seg)


def get_vision_prompt(timestamp: float, version: str = None) -> str:
    """버전에 해당하는 비전 프롬프트를 반환한다. timestamp를 포매팅한다."""
    v = version or CURRENT_VISION_VERSION
    template = VISION_PROMPTS[v]
    return template.format(timestamp=timestamp)


def get_qa_system_prompt(version: str = None) -> str:
    """버전에 해당하는 QA 시스템 프롬프트를 반환한다."""
    v = version or CURRENT_QA_SYSTEM_VERSION
    return QA_SYSTEM_PROMPTS[v]


def get_eval_answer_relevance_prompt(version: str = None) -> str:
    v = version or CURRENT_EVAL_ANSWER_RELEVANCE_VERSION
    return EVAL_ANSWER_RELEVANCE_PROMPTS[v]


def get_eval_groundedness_prompt(version: str = None) -> str:
    v = version or CURRENT_EVAL_GROUNDEDNESS_VERSION
    return EVAL_GROUNDEDNESS_PROMPTS[v]


def get_eval_retrieval_precision_prompt(version: str = None) -> str:
    v = version or CURRENT_EVAL_RETRIEVAL_PRECISION_VERSION
    return EVAL_RETRIEVAL_PRECISION_PROMPTS[v]


def get_eval_visual_text_alignment_prompt(version: str = None) -> str:
    v = version or CURRENT_EVAL_VISUAL_TEXT_ALIGNMENT_VERSION
    return EVAL_VISUAL_TEXT_ALIGNMENT_PROMPTS[v]
