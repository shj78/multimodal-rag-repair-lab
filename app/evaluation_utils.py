"""
evaluation_utils.py — 멀티모달 RAG 평가 유틸리티

[TODO]
평가 지표 4종을 구현하세요. calculate_wer와 run_full_evaluation은 뼈대가 제공됩니다.

평가 지표 목표치:
    WER (↓)                < 0.15
    Answer Relevance (↑)   > 0.70
    Groundedness (↑)       > 0.70
    Retrieval Precision (↑) > 0.60

[선택 과제] calculate_visual_text_alignment — 이 파일 하단 참고
"""

from typing import List, Dict, Any, Optional, Tuple
import requests
import re
from jiwer import wer, cer

from app.chat_utils import get_answer_by_chat_model
from app.retrieval_utils import retrieve_segments

from app.config import CONFIG
from app.prompts import (
    EVAL_ANSWER_RELEVANCE_PROMPT,
    EVAL_GROUNDEDNESS_PROMPT,
    EVAL_RETRIEVAL_PRECISION_PROMPT,
    EVAL_VISUAL_TEXT_ALIGNMENT_PROMPT,
)


def _llm_chat(prompt: str) -> str:
    """평가용 LLM 호출 헬퍼 — provider에 따라 분기."""
    if CONFIG.provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=CONFIG.openai_api_key)
        resp = client.chat.completions.create(
            model=CONFIG.openai_chat_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    else:
        resp = requests.post(
            f"{CONFIG.ollama_base}/api/chat",
            json={
                "model": CONFIG.ollama_chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
        )
        return resp.json()["message"]["content"].strip()


# ────────────────────────────────────────
# WER + CER 계산
# ────────────────────────────────────────
def calculate_wer_cer(reference: str, hypothesis: str) -> Tuple[float, float]:
    """
    Word Error Rate(단어 오류율)과 Character Error Rate(문자 오류율)을 함께 계산합니다.

    WER = (S + D + I) / N  (단어 단위)
    CER = (S + D + I) / N  (문자 단위)

    한국어에서는 띄어쓰기·조사 차이로 WER이 과대평가되는 경향이 있어
    CER을 함께 보면 체감 품질에 더 가까운 판단이 가능합니다.

    Args:
        reference (str): 정답 전사 텍스트 (직접 받아쓰기)
        hypothesis (str): faster-whisper 또는 Whisper API 전사 결과

    Returns:
        Tuple[float, float]: (WER, CER) — 0.0 = 완벽, 1.0 = 전혀 다름
    """
    return wer(reference, hypothesis), cer(reference, hypothesis)


# ────────────────────────────────────────
# [TODO] LLM-as-Judge 평가 함수들
# ────────────────────────────────────────
def calculate_answer_relevance(question: str, answer: str) -> float:
    """
    [TODO] LLM-as-Judge 방식으로 답변의 질문 관련성을 평가합니다.

    요구사항:
    1. LLM(Ollama 또는 OpenAI)에게 아래 구조의 프롬프트를 전달하세요.
    2. 0.0~1.0 사이의 점수를 반환하도록 프롬프트를 설계하세요.
    3. LLM 응답에서 숫자를 파싱하여 float로 반환하세요.

    프롬프트 설계 예시:
        "다음 질문과 답변의 관련성을 0.0~1.0으로 평가하세요.
         관련성이 없으면 0.0, 완전히 관련 있으면 1.0입니다.
         숫자만 반환하세요.
         질문: {question}
         답변: {answer}"

    Args:
        question (str): 사용자 질문
        answer (str): LLM 생성 답변

    Returns:
        float: 관련성 점수 (0.0~1.0)
    """
    # ---------------------------------------------------------
    # [TODO] LLM 호출 후 점수 파싱
    #
    # ── LLM 호출 힌트 ────────────────────────────────────────
    # prompt = (
    #     f"다음 질문과 답변의 관련성을 0.0~1.0으로 평가하세요.\n"
    #     f"관련성이 없으면 0.0, 완전히 관련 있으면 1.0입니다.\n"
    #     f"숫자만 반환하세요.\n"
    #     f"질문: {question}\n답변: {answer}"
    # )
    #
    # [Ollama (PROVIDER=local)]
    #     import os, requests
    #     OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
    #     OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.1")
    #     resp = requests.post(
    #         f"{OLLAMA_BASE}/api/chat",
    #         json={"model": OLLAMA_CHAT_MODEL,
    #               "messages": [{"role": "user", "content": prompt}],
    #               "stream": False},
    #     )
    #     raw = resp.json()["message"]["content"].strip()
    #
    # [OpenAI (PROVIDER=openai)]
    #     from openai import OpenAI
    #     import os
    #     OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
    #     client = OpenAI()
    #     resp = client.chat.completions.create(
    #         model=OPENAI_CHAT_MODEL,
    #         messages=[{"role": "user", "content": prompt}],
    #     )
    #     raw = resp.choices[0].message.content.strip()
    #
    # # 숫자 파싱 (LLM이 "0.85" 또는 "Score: 0.85" 형식으로 반환할 수 있음)
    # import re
    # match = re.search(r"\d+\.?\d*", raw)
    # return float(match.group()) if match else 0.0
    # ---------------------------------------------------------

    prompt = EVAL_ANSWER_RELEVANCE_PROMPT.format(question=question, answer=answer)
    raw = _llm_chat(prompt)
    match = re.search(r"\d+\.?\d*", raw)
    return float(match.group()) if match else 0.0


def calculate_groundedness(answer: str, context: str) -> float:
    """
    [TODO] LLM-as-Judge 방식으로 답변의 근거성(hallucination 여부)을 평가합니다.

    요구사항:
    1. 답변이 context(검색된 세그먼트 텍스트)에 근거하는지 0.0~1.0으로 평가합니다.
    2. context에 없는 내용을 답변에 포함하면 낮은 점수를 줘야 합니다.

    프롬프트 설계 포인트:
        - "답변의 모든 내용이 주어진 컨텍스트에서 찾을 수 있습니까?"
        - "컨텍스트에 없는 내용을 답변이 생성했다면 점수를 낮게 주세요."

    Args:
        answer (str): LLM 생성 답변
        context (str): 검색된 세그먼트 텍스트(컨텍스트)

    Returns:
        float: 근거성 점수 (0.0~1.0)
    """
    # ---------------------------------------------------------
    # [TODO] LLM 호출 후 점수 파싱
    #
    # ── LLM 호출 힌트 ────────────────────────────────────────
    # prompt = (
    #     f"아래 답변이 주어진 컨텍스트에만 근거하는지 0.0~1.0으로 평가하세요.\n"
    #     f"컨텍스트에 없는 내용이 답변에 포함되어 있으면 낮은 점수를 주세요.\n"
    #     f"숫자만 반환하세요.\n"
    #     f"컨텍스트: {context}\n답변: {answer}"
    # )
    # calculate_answer_relevance()의 LLM 호출 패턴과 동일하게 구현하세요.
    # ---------------------------------------------------------

    prompt = EVAL_GROUNDEDNESS_PROMPT.format(context=context, answer=answer)
    raw = _llm_chat(prompt)
    match = re.search(r"\d+\.?\d*", raw)
    return float(match.group()) if match else 0.0


def calculate_retrieval_precision(
    retrieved_segments: List[Dict], question: str
) -> float:
    """
    [TODO] 검색된 세그먼트 중 질문과 관련 있는 세그먼트의 비율을 평가합니다.

    요구사항:
    1. 각 retrieved_segments에 대해 LLM에게 질문과 관련이 있는지(0 또는 1) 판단하게 합니다.
    2. 관련 세그먼트 수 / 전체 검색 세그먼트 수를 반환합니다.
    3. retrieved_segments가 비어 있으면 0.0을 반환합니다.

    Args:
        retrieved_segments (List[Dict]): search_similar_segments() 반환값
        question (str): 사용자 질문

    Returns:
        float: Retrieval Precision (0.0~1.0)
    """
    # ---------------------------------------------------------
    # [TODO] 각 세그먼트에 대한 관련성 판단 후 비율 계산
    #
    # ── LLM 호출 힌트 ────────────────────────────────────────
    # if not retrieved_segments:
    #     return 0.0
    #
    # relevant_count = 0
    # for seg in retrieved_segments:
    #     prompt = (
    #         f"다음 질문에 대해 아래 텍스트가 관련이 있으면 1, 없으면 0을 반환하세요.\n"
    #         f"숫자만 반환하세요.\n"
    #         f"질문: {question}\n텍스트: {seg.get('text', '')}"
    #     )
    #     # calculate_answer_relevance()의 LLM 호출 패턴과 동일하게 구현하세요.
    #     # score = <LLM 호출 결과 파싱>
    #     # relevant_count += 1 if score >= 0.5 else 0
    #
    # return relevant_count / len(retrieved_segments)
    # ---------------------------------------------------------

    if not retrieved_segments:
        return 0.0

    relevant_count = 0
    for seg in retrieved_segments:
        prompt = EVAL_RETRIEVAL_PRECISION_PROMPT.format(
            question=question, text=seg.get("text", "")
        )
        raw = _llm_chat(prompt)
        match = re.search(r"\d+\.?\d*", raw)
        score = float(match.group()) if match else 0.0

        relevant_count += 1 if score >= 0.5 else 0

    return relevant_count / len(retrieved_segments)


# ────────────────────────────────────────
# [부분 스캐폴드] 전체 평가 실행
# ────────────────────────────────────────
def run_full_evaluation(
    media_id: str,
    test_questions: List[str],
    reference_transcript: Optional[str] = None,
) -> Dict[str, Any]:
    """
    [부분 스캐폴드] 전체 평가 파이프라인을 실행하고 메트릭을 반환합니다.

    이 함수의 루프 구조는 제공됩니다.
    TODO 표시된 부분에서 각 평가 함수를 호출하세요.

    Args:
        media_id (str): 평가 대상 미디어 ID
        test_questions (List[str]): 평가에 사용할 질문 목록 (최소 1개)
        reference_transcript (str | None): WER 계산용 정답 텍스트

    Returns:
        Dict: {
            "metrics": { wer, cer, answer_relevance, groundedness, retrieval_precision },
            "qa_results": [ per-question detail ... ],
            "question_count": int,
        }
    """
    import time

    from .media_utils import get_text_embedding
    from .supabase_utils import (
        get_media_segments,
        get_media_by_id,
    )

    relevance_scores: List[float] = []
    groundedness_scores: List[float] = []
    precision_scores: List[float] = []
    qa_results: List[Dict[str, Any]] = []

    for question_index, question in enumerate(test_questions, start=1):
        question_start = time.perf_counter()

        # 1. 임베딩 + 검색 + 선별 (rerank/threshold)
        query_embedding = get_text_embedding(question)
        all_segments, accepted_segments = retrieve_segments(
            question, query_embedding, media_id
        )

        # 2. 답변 생성
        answer, context_text = get_answer_by_chat_model(question, accepted_segments)

        # 3. 메트릭 계산
        relevance = calculate_answer_relevance(question, answer)
        groundedness = calculate_groundedness(answer, context_text)
        precision = calculate_retrieval_precision(accepted_segments, question)

        relevance_scores.append(relevance)
        groundedness_scores.append(groundedness)
        precision_scores.append(precision)

        question_latency = round((time.perf_counter() - question_start) * 1000)

        qa_results.append(
            {
                "test_id": f"Q{question_index}",
                "query": question,
                "answer": answer,
                "context_text": context_text,
                "sources": [
                    {
                        "chunk_index": seg.get("chunk_index"),
                        "similarity": seg.get("similarity"),
                        "accepted": seg.get("accepted", True),
                        "text": seg.get("text", "")[:200],
                    }
                    for seg in all_segments
                ],
                "metrics": {
                    "answer_relevance": relevance,
                    "groundedness": groundedness,
                    "retrieval_precision": precision,
                },
                "latency_ms": question_latency,
            }
        )

    def _avg(lst: List[float]) -> float:
        return sum(lst) / len(lst) if lst else 0.0

    wer_score = None
    cer_score = None
    if reference_transcript:
        media = get_media_by_id(media_id)
        full_transcript = media.get("full_transcript") if media else None
        if not full_transcript:
            # fallback: full_transcript 컬럼이 없는 기존 데이터
            segments = get_media_segments(media_id)
            full_transcript = " ".join([seg.get("text", "") for seg in segments])
        wer_score, cer_score = calculate_wer_cer(reference_transcript, full_transcript)

    # [선택 과제] Visual-Text Alignment
    alignment_scores: List[float] = []
    all_segments = get_media_segments(media_id)
    for seg in all_segments:
        desc = seg.get("frame_description")
        text = seg.get("text", "")
        if desc and text:
            alignment_scores.append(calculate_visual_text_alignment(desc, text))

    return {
        "metrics": {
            "wer": wer_score,
            "cer": cer_score,
            "answer_relevance": _avg(relevance_scores),
            "groundedness": _avg(groundedness_scores),
            "retrieval_precision": _avg(precision_scores),
            "visual_text_alignment": (
                _avg(alignment_scores) if alignment_scores else None
            ),
        },
        "qa_results": qa_results,
        "question_count": len(test_questions),
    }


# ────────────────────────────────────────
# [선택 과제] Visual-Text Alignment
# ────────────────────────────────────────
def calculate_visual_text_alignment(
    frame_description: str, transcript_text: str
) -> float:
    """
    [선택 과제] 비전 모델이 생성한 프레임 설명과 전사 텍스트의 일치도를 평가합니다.

    목표치: > 0.65

    이 함수는 필수 과제가 아닙니다. 아래 가이드를 따라 선택적으로 구현하세요.

    구현 아이디어:
    1. LLM-as-Judge: "아래 영상 설명과 음성 전사가 같은 장면을 묘사합니까? 0.0~1.0으로 점수를 주세요."
    2. 임베딩 코사인 유사도: get_text_embedding(frame_description)과
       get_text_embedding(transcript_text)의 코사인 유사도 계산

    주의: PROVIDER=openai인 경우 GPT-4o Vision 추가 호출 비용이 발생합니다.

    Args:
        frame_description (str): analyze_frame_with_vision_model() 반환값
        transcript_text (str): 동일 구간의 전사 텍스트

    Returns:
        float: 정렬 점수 (0.0~1.0)
    """
    prompt = EVAL_VISUAL_TEXT_ALIGNMENT_PROMPT.format(
        frame_description=frame_description, transcript_text=transcript_text
    )
    raw = _llm_chat(prompt)
    match = re.search(r"\d+\.?\d*", raw)
    score = float(match.group()) if match else 0.0

    return min(max(score, 0.0), 1.0)
