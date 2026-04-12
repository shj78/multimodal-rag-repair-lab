from typing import List, Dict
import ffmpeg

from faster_whisper import WhisperModel
from app.config import TranscriptionCfg, get_stage_config
from app.prompts import get_transcription_prompt


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
    initial_prompt = get_transcription_prompt(cfg.whisper_prompt_version)

    if cfg.provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=cfg.openai_api_key)
        with open(audio_path, "rb") as f:
            kwargs = dict(
                model=cfg.openai_whisper_model,
                file=f,
                response_format="verbose_json",
            )
            if initial_prompt:
                kwargs["prompt"] = initial_prompt
            resp = client.audio.transcriptions.create(**kwargs)
        return [
            {"start": seg.start, "end": seg.end, "text": seg.text}
            for seg in resp.segments
        ]
    else:
        model = WhisperModel(
            cfg.whisper_model_size, device="cpu", compute_type="int8"
        )
        transcribe_kwargs: dict = {"beam_size": 5}
        if initial_prompt:
            transcribe_kwargs["initial_prompt"] = initial_prompt
        segments, _ = model.transcribe(audio_path, **transcribe_kwargs)
        return [
            {"start": seg.start, "end": seg.end, "text": seg.text} for seg in segments
        ]
