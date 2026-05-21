from app.qa.chat import strip_thinking_blocks


def test_strip_thinking_blocks_removes_scratchpad():
    answer = """<thinking>
1) 수집: 내부 메모
</thinking>

답변:
9초 지점에서 사람이 차량 앞에 접근했습니다."""

    assert strip_thinking_blocks(answer) == "답변:\n9초 지점에서 사람이 차량 앞에 접근했습니다."


def test_strip_thinking_blocks_keeps_plain_answer():
    answer = "답변:\n확인되지 않습니다."

    assert strip_thinking_blocks(answer) == answer
