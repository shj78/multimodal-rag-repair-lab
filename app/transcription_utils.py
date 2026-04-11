"""
transcription_utils.py — 오디오/비디오 전사 유틸리티

[TODO]
이 파일의 두 함수를 구현하세요.
구현 순서: extract_audio_from_video → transcribe_audio
"""

from typing import List, Dict
import ffmpeg

from faster_whisper import WhisperModel
from app.config import CONFIG


def extract_audio_from_video(video_path: str, output_path: str) -> str:
    """
    [TODO] 비디오 파일에서 오디오를 추출합니다.

    요구사항:
    1. ffmpeg-python 라이브러리를 사용하여 비디오에서 오디오를 WAV 형식으로 추출하세요.
       - Pipfile에 설치된 ffmpeg-python 패키지의 사용법을 직접 조사하세요.
       - 시스템에 ffmpeg 바이너리가 설치되어 있어야 합니다 (README 환경 설정 참고).
    2. 오디오는 16000Hz 모노 WAV로 추출하세요 (faster-whisper 권장 포맷).
    3. 비디오가 아닌 파일(오디오 파일)이 들어올 경우 예외 없이 동작해야 합니다.

    힌트:
        import ffmpeg
        ffmpeg.input(video_path).output(output_path, ar=16000, ac=1).run(overwrite_output=True)

    Args:
        video_path (str): 원본 비디오 파일 경로
        output_path (str): 추출된 오디오 저장 경로 (.wav)

    Returns:
        str: 저장된 오디오 파일 경로 (output_path와 동일)
    """

    (
        ffmpeg.input(video_path)
        .output(output_path, ar=16000, ac=1)
        .run(overwrite_output=True)
    )

    # ---------------------------------------------------------
    # [TODO] 오디오 추출 로직 작성
    # ---------------------------------------------------------
    pass


def transcribe_audio(audio_path: str) -> List[Dict]:
    """
    [TODO] 오디오 파일을 전사하여 타임스탬프 포함 세그먼트 목록을 반환합니다.

    요구사항:
    1. faster-whisper 라이브러리를 사용하여 오디오를 전사하세요.
       - 모델 크기는 config.py의 WHISPER_MODEL_SIZE를 사용하세요.
       - 공식 문서/예제를 조사하여 WhisperModel 초기화와 transcribe() 호출 방법을 파악하세요.
    2. 반환값은 각 세그먼트를 {"start": float, "end": float, "text": str} 형태로 담은 리스트입니다.
    3. PROVIDER=openai인 경우 OpenAI Whisper API를 사용하세요.
       - openai.audio.transcriptions.create() 메서드 조사 (response_format="verbose_json")

    힌트 (로컬):
        from faster_whisper import WhisperModel
        from app.config import WHISPER_MODEL_SIZE
        model = WhisperModel(CONFIG.whisper_model_size, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(audio_path, beam_size=5)
        # segments는 제너레이터 — list()로 변환 후 사용

    ⚠️ CPU 전사 소요 시간 안내:
        2분 오디오 → 약 1~3분 소요 (머신 성능에 따라 다름)
        처음 테스트는 반드시 2~3분 이하 파일로 시작하세요.

    Args:
        audio_path (str): 전사할 오디오 파일 경로

    Returns:
        List[Dict]: [{"start": 0.0, "end": 2.5, "text": "안녕하세요."}, ...]
    """

    if CONFIG.provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=CONFIG.openai_api_key)
        with open(audio_path, "rb") as f:
            resp = client.audio.transcriptions.create(
                model=CONFIG.openai_whisper_model,
                file=f,
                response_format="verbose_json",
            )
        return [
            {"start": seg.start, "end": seg.end, "text": seg.text}
            for seg in resp.segments
        ]
    else:
        model = WhisperModel(
            CONFIG.whisper_model_size, device="cpu", compute_type="int8"
        )
        segments, _ = model.transcribe(audio_path, beam_size=5)
        return [
            {"start": seg.start, "end": seg.end, "text": seg.text} for seg in segments
        ]
