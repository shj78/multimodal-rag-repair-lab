"""
ingest_pipeline.py — 미디어 1건의 ingest 오케스트레이션 (route와 util 사이의 pipeline 층)

main.py:process_media_background에 붙어 있던 "audio 추출 → 전사 → 프레임 분석 →
교정 → 청킹/임베딩/저장" 흐름을 하나로 모은 pipeline. qa_pipeline.run_qa와 짝을
이루는 두 번째 pipeline으로 pipelines/ 폴더가 성립한다.

LangSmith trace 구조 (이름 규칙: 루트는 도메인 prefix만, 말단은 번호):
    ingest.request (root, chain)
      ├─ ingest.1_audio_extract    (tool)
      ├─ ingest.2_transcribe       (tool)
      ├─ ingest.3_extract_frames   (tool)
      ├─ ingest.4_analyze_frame    (tool) × 프레임 수
      ├─ ingest.5_correct          (tool)
      ├─ ingest.6_chunk            (tool)
      └─ per-chunk 루프:
          ├─ ingest.7_multimodal    (tool)
          └─ ingest.8_embed_chunk   (embedding)
"""

import os
from typing import Any, Dict, List

from langsmith import traceable
from openai import AuthenticationError as OpenAIAuthError

from ..config import CONFIG, get_stage_config
from ..diagnostics import StageTimer, get_config_snapshot
from ..embedding import embed_chunk
from ..ingest.chunking import segment_transcript
from ..ingest.correction import correct_transcription_with_vision
from ..ingest.multimodal import combine_multimodal_context
from ..ingest.transcription import extract_audio_from_video, transcribe_audio
from ..ingest.vision import analyze_frame_with_vision_model, extract_key_frames
from ..supabase_utils import (
    SupabaseOperationError,
    save_media_file,
    save_segment,
    update_media_status,
)


_VIDEO_EXTS = {"mp4", "mov", "avi", "mkv", "webm"}


def _is_video_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _VIDEO_EXTS


@traceable(name="ingest.request", run_type="chain")
def run_ingest(
    job_id: str,
    media_id: str,
    file_path: str,
    filename: str,
    job_store: Dict[str, Dict[str, Any]],
) -> None:
    """미디어 1건을 전사·비전·교정·임베딩 단계로 돌려 저장까지 마친다.

    job_store에 status 전이(transcribing → analyzing_frames → embedding → ready/failed)와
    최종 결과(media_id, latency_ms, stats, error)를 in-place로 기록한다. HTTP 상태 관리는
    route 레이어가 담당하지만, 파이프라인 진행 상태 전이 자체는 오케스트레이션 내부 관심사라
    이 함수 안에서 갱신한다.
    """
    try:
        is_video = _is_video_file(filename)
        st = StageTimer()

        job_store[job_id]["config"] = get_config_snapshot()

        with st.measure("audio_extract"):
            if is_video:
                audio_path = os.path.join(CONFIG.upload_dir, f"{media_id}_audio.wav")
                extract_audio_from_video(file_path, audio_path)
            else:
                audio_path = file_path

        job_store[job_id]["status"] = "transcribing"
        with st.measure("transcribe"):
            segments = transcribe_audio(audio_path)

        duration = segments[-1]["end"] if segments else 0.0
        full_transcript = " ".join(seg["text"].strip() for seg in segments)
        save_media_file(
            media_id=media_id,
            filename=filename,
            file_type="video" if is_video else "audio",
            duration=duration,
            metadata={"provider": get_stage_config().transcription.provider},
            full_transcript=full_transcript,
            file_path=file_path,
        )

        frame_analyses: List[Dict[str, Any]] = []
        frame_count = 0
        if is_video:
            job_store[job_id]["status"] = "analyzing_frames"
            with st.measure("vision_total"):
                frames_dir = os.path.join(CONFIG.frames_dir, media_id)
                os.makedirs(frames_dir, exist_ok=True)
                frames = extract_key_frames(
                    file_path,
                    frames_dir,
                    frames_per_minute=get_stage_config().vision.frames_per_minute,
                )
                frame_count = len(frames)
                for frame in frames:
                    description = analyze_frame_with_vision_model(
                        frame["frame_path"], frame["timestamp"]
                    )
                    frame_analyses.append(
                        {"timestamp": frame["timestamp"], "description": description}
                    )

        segments = correct_transcription_with_vision(segments, frame_analyses)

        job_store[job_id]["status"] = "embedding"
        with st.measure("embed_save"):
            chunks = segment_transcript(segments)

            for chunk in chunks:
                context_text = combine_multimodal_context(
                    [chunk], frame_analyses, chunk["start"], chunk["end"]
                )

                embedding = embed_chunk(context_text)
                frame_desc = next(
                    (
                        f["description"]
                        for f in frame_analyses
                        if chunk["start"] <= f["timestamp"] <= chunk["end"]
                    ),
                    None,
                )
                save_segment(
                    media_id=media_id,
                    chunk_index=chunk["chunk_index"],
                    text=chunk["text"],
                    start_time=chunk["start"],
                    end_time=chunk["end"],
                    embedding=embedding,
                    frame_description=frame_desc,
                )

        update_media_status(media_id, "ready", segment_count=len(chunks))

        job_store[job_id]["status"] = "ready"
        job_store[job_id]["media_id"] = media_id
        job_store[job_id]["latency_ms"] = st.result
        job_store[job_id]["stats"] = {
            "duration_seconds": duration,
            "segment_count": len(chunks),
            "frame_count": frame_count,
        }

    except OpenAIAuthError:
        job_store[job_id]["status"] = "failed"
        job_store[job_id]["error"] = (
            "OpenAI API 키가 유효하지 않습니다. OPENAI_API_KEY를 확인하세요."
        )
        try:
            update_media_status(media_id, "failed")
        except Exception:
            pass
    except SupabaseOperationError as e:
        job_store[job_id]["status"] = "failed"
        job_store[job_id]["error"] = str(e)
    except Exception as e:
        job_store[job_id]["status"] = "failed"
        job_store[job_id]["error"] = str(e)
        try:
            update_media_status(media_id, "failed")
        except Exception:
            pass
        raise
