from typing import List, Dict
import ffmpeg

from faster_whisper import WhisperModel
from app.config import TranscriptionCfg, get_stage_config


def extract_audio_from_video(video_path: str, output_path: str) -> str:
    (
        ffmpeg.input(video_path)
        .output(output_path, ar=16000, ac=1)
        .run(overwrite_output=True)
    )
    pass


def transcribe_audio(
    audio_path: str, cfg: TranscriptionCfg | None = None
) -> List[Dict]:
    cfg = cfg or get_stage_config().transcription
    if cfg.provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=cfg.openai_api_key)
        with open(audio_path, "rb") as f:
            resp = client.audio.transcriptions.create(
                model=cfg.openai_whisper_model,
                file=f,
                response_format="verbose_json",
            )
        return [
            {"start": seg.start, "end": seg.end, "text": seg.text}
            for seg in resp.segments
        ]
    else:
        model = WhisperModel(
            cfg.whisper_model_size, device="cpu", compute_type="int8"
        )
        segments, _ = model.transcribe(audio_path, beam_size=5)
        return [
            {"start": seg.start, "end": seg.end, "text": seg.text} for seg in segments
        ]
