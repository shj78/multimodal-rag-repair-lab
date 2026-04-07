"""
Track A (RAG) 전용 스타터 평가 스크립트
※ Track B (멀티모달)는 프로젝트에 포함된 evaluation_utils.py를 사용하세요.

사용법:
1. pip install requests  (최초 1회)
2. test_questions.json 파일을 작성합니다 (아래 형식 참고)
3. 서버가 실행 중인지 확인합니다
4. python eval.py 실행

test_questions.json 형식:
[
    {
        "question": "PDF 3페이지 표에서 2024년 매출 합계는?",
        "expected": "1,200억원",
        "category": "table"
    },
    {
        "question": "보고서의 차트에서 가장 높은 수치는?",
        "expected": "150억",
        "category": "image"
    },
    {
        "question": "이 보고서에서 CEO의 취미는?",
        "expected": "REFUSE",
        "category": "hallucination"
    }
]

category 값: "table", "image", "keyword", "hallucination", "general"
expected가 "REFUSE"이면 시스템이 거부해야 하는 질문입니다.
"""

import json
import sys
import time
from pathlib import Path

import requests

BASE_URL = "http://127.0.0.1:8000"
QUESTIONS_FILE = "test_questions.json"
DOCUMENT_ID = None  # 스프린트 2 (RAG)에서는 업로드한 문서의 ID를 여기에 설정하세요 (예: "abc-123")

REFUSAL_KEYWORDS = [
    "없습니다", "포함되어 있지 않", "확인되지 않", "찾을 수 없",
    "해당 정보", "관련 내용이 없", "답변할 수 없",
]


def load_questions(path: str = QUESTIONS_FILE) -> list[dict]:
    filepath = Path(path)
    if not filepath.exists():
        print(f"[오류] {path} 파일이 없습니다.")
        print("test_questions.json 파일을 먼저 작성하세요. (상단 docstring 참고)")
        sys.exit(1)

    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def ask_question(question: str, document_id: str = None) -> dict:
    # 이 스크립트는 Track A (RAG) 전용입니다.
    # Track B (멀티모달)는 기존 evaluation_utils.py를 사용하세요.
    # 스프린트 2 (RAG)에서는 document_id가 필수입니다 — 상단 DOCUMENT_ID 상수를 설정하세요.
    payload = {"query": question}
    if document_id:
        payload["document_id"] = document_id

    try:
        resp = requests.post(f"{BASE_URL}/qa", json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        print(f"[오류] 서버에 연결할 수 없습니다. {BASE_URL} 에서 서버가 실행 중인지 확인하세요.")
        sys.exit(1)
    except Exception as e:
        return {"answer": f"[ERROR] {e}", "error": True}


def is_refusal(answer: str) -> bool:
    return any(kw in answer for kw in REFUSAL_KEYWORDS)


def evaluate(questions: list[dict], document_id: str = None) -> dict:
    results = []
    category_stats: dict[str, dict] = {}

    print(f"\n{'='*60}")
    print(f"평가 시작: {len(questions)}개 질문")
    print(f"{'='*60}\n")

    for i, q in enumerate(questions, 1):
        question = q["question"]
        expected = q.get("expected", "")
        category = q.get("category", "general")

        print(f"[{i}/{len(questions)}] {question[:50]}...")

        start = time.time()
        response = ask_question(question, document_id)
        elapsed = time.time() - start

        answer = response.get("answer", "")
        got_refusal = is_refusal(answer)
        expected_refusal = expected.upper() == "REFUSE"

        if expected_refusal:
            correct = got_refusal
        elif got_refusal:
            correct = False
        else:
            correct = None  # 수동 판정 필요

        result = {
            "question": question,
            "expected": expected,
            "answer": answer[:200],
            "category": category,
            "correct": correct,
            "is_refusal": got_refusal,
            "expected_refusal": expected_refusal,
            "elapsed_ms": round(elapsed * 1000),
        }
        results.append(result)

        if category not in category_stats:
            category_stats[category] = {"total": 0, "auto_correct": 0, "manual_needed": 0}
        category_stats[category]["total"] += 1
        if correct is True:
            category_stats[category]["auto_correct"] += 1
        elif correct is None:
            category_stats[category]["manual_needed"] += 1

        status = "O" if correct else ("?" if correct is None else "X")
        print(f"  [{status}] {elapsed:.1f}s | {answer[:80]}...")
        print()

    return {"results": results, "category_stats": category_stats}


def print_summary(evaluation: dict):
    results = evaluation["results"]
    stats = evaluation["category_stats"]

    total = len(results)
    auto_correct = sum(1 for r in results if r["correct"] is True)
    auto_wrong = sum(1 for r in results if r["correct"] is False)
    manual = sum(1 for r in results if r["correct"] is None)
    avg_ms = sum(r["elapsed_ms"] for r in results) / total if total else 0

    print(f"\n{'='*60}")
    print("평가 결과 요약")
    print(f"{'='*60}")
    print(f"  총 질문 수:          {total}")
    print(f"  자동 판정 정답:      {auto_correct}")
    print(f"  자동 판정 오답:      {auto_wrong}")
    print(f"  수동 판정 필요:      {manual}")
    if (auto_correct + auto_wrong) > 0:
        print(f"  자동 정확도:         {auto_correct / (auto_correct + auto_wrong) * 100:.1f}%")
    else:
        print(f"  자동 정확도:         N/A")
    print(f"  평균 응답 시간:      {avg_ms:.0f}ms")

    print(f"\n카테고리별:")
    for cat, s in stats.items():
        print(f"  [{cat}] 총 {s['total']}개, 자동 정답 {s['auto_correct']}개, 수동 필요 {s['manual_needed']}개")

    print(f"\n{'='*60}")
    print("참고: correct=None(?) 항목은 수동으로 정답 여부를 판정해야 합니다.")
    print("      expected='REFUSE' 항목만 자동 판정됩니다.")
    print(f"{'='*60}")

    # ----------------------------------------------------------------
    # 확장 포인트: 여기에 RAGAS 또는 LLM-as-Judge 지표를 추가하세요
    #
    # 예시 (RAGAS):
    #   from ragas import evaluate as ragas_eval
    #   ragas_result = ragas_eval(dataset, metrics=[faithfulness, answer_relevancy])
    #
    # 예시 (LLM-as-Judge):
    #   for r in results:
    #       r["judge_score"] = llm_judge(r["question"], r["answer"])
    # ----------------------------------------------------------------


def save_results(evaluation: dict, output_path: str = "eval_results.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evaluation, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {output_path}")


if __name__ == "__main__":
    questions = load_questions()
    evaluation = evaluate(questions, document_id=DOCUMENT_ID)
    print_summary(evaluation)
    save_results(evaluation)
