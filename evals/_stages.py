"""
_stages.py — 파이프라인 단계별 실행 함수

각 함수는 app/ 모듈을 호출하고, 결과 + 소요시간을 반환한다.
fixture 저장도 여기서 처리한다.
"""

import os
import shutil
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.config import get_stage_config

from evals._common import EVALS_DIR, save_fixture, timer

# ── transcribe ──


def run_transcribe(
    source_path: str, dataset: str, config_snapshot: dict
) -> Tuple[List[Dict], int]:
    """오디오 추출 → 전사 → segments fixture 저장.

    Returns:
        (segments, latency_ms)
    """
    # lazy import: faster-whisper 모델 로딩이 무거우므로 실행 시점까지 지연
    from app.ingest.transcription import extract_audio_from_video, transcribe_audio

    print("[transcribe] 오디오 추출 중...")
    base, _ = os.path.splitext(source_path)
    audio_path = f"{base}_audio.wav"
    with timer() as t_audio:
        extract_audio_from_video(source_path, audio_path)
    print(f"[transcribe] 오디오 추출 완료 ({t_audio()}ms)")

    print("[transcribe] 전사 중...")
    with timer() as t_transcribe:
        segments = transcribe_audio(audio_path)
    print(f"[transcribe] 전사 완료: {len(segments)}개 세그먼트 ({t_transcribe()}ms)")

    save_fixture(
        "segments",
        dataset,
        segments,
        {
            "transcription_provider": config_snapshot["transcription_provider"],
            "whisper_model_size": config_snapshot["whisper_model_size"],
            "openai_whisper_model": config_snapshot["openai_whisper_model"],
            "whisper_prompt_version": config_snapshot.get("whisper_prompt_version", ""),
        },
        latency_ms=t_transcribe(),
    )

    if os.path.exists(audio_path):
        os.remove(audio_path)

    return segments, t_transcribe()


# ── vision ──


def run_vision(
    source_path: str, dataset: str, config_snapshot: dict
) -> Tuple[List[Dict], int]:
    """프레임 추출 → 비전 분석 → frame_analyses fixture 저장.

    Returns:
        (frame_analyses, latency_ms)
    """
    # lazy import: cv2 + ollama 비전 호출이 무거우므로 실행 시점까지 지연
    from app.ingest.vision import analyze_frame_with_vision_model, extract_key_frames

    frames_dir = str(EVALS_DIR / "temp_frames" / dataset)
    os.makedirs(frames_dir, exist_ok=True)

    print("[vision] 프레임 추출 중...")
    frames = extract_key_frames(
        source_path, frames_dir, frames_per_minute=get_stage_config().vision.frames_per_minute
    )
    print(f"[vision] {len(frames)}개 프레임 추출 완료")

    print("[vision] 비전 분석 중...")
    frame_analyses = []
    with timer() as t_vision:
        for i, frame in enumerate(frames, 1):
            with timer() as t_frame:
                description = analyze_frame_with_vision_model(
                    frame["frame_path"], frame["timestamp"]
                )
            frame_analyses.append(
                {
                    "timestamp": frame["timestamp"],
                    "description": description,
                    "latency_ms": t_frame(),
                }
            )
            print(f"  [{i}/{len(frames)}] {frame['timestamp']:.1f}s ({t_frame()}ms)")

    print(f"[vision] 비전 분석 완료 ({t_vision()}ms)")

    save_fixture(
        "frame_analyses",
        dataset,
        frame_analyses,
        {
            "vision_provider": config_snapshot["vision_provider"],
            "vision_model": config_snapshot["vision_model"],
            "prompt_version": config_snapshot["prompt_version"],
            "frames_per_minute": config_snapshot["frames_per_minute"],
        },
        latency_ms=t_vision(),
    )

    if os.path.exists(frames_dir):
        shutil.rmtree(frames_dir)

    return frame_analyses, t_vision()


# ── embed ──


def run_embed_and_save(
    segments: List[Dict], frame_analyses: List[Dict], config_snapshot: dict
) -> Tuple[str, int]:
    """Vision-guided 교정 → 청킹 + 임베딩 + DB 저장.

    Returns:
        (media_id, latency_ms)
    """
    from app.ingest.correction import correct_transcription_with_vision
    from app.media_utils import (
        combine_multimodal_context,
        get_text_embedding,
        segment_transcript,
    )
    from app.supabase_utils import save_media_file, save_segment, update_media_status

    # ── correction (enabled 시에만) ──
    correction_cfg = get_stage_config().correction
    if correction_cfg.enabled and frame_analyses:
        print("[embed] Vision-guided 전사 교정 중...")
        with timer() as t_correction:
            segments = correct_transcription_with_vision(segments, frame_analyses, correction_cfg)
        print(f"[embed] 교정 완료 ({t_correction()}ms)")

    media_id = str(uuid.uuid4())

    print(f"[embed] 청킹 + 임베딩 중... (media_id={media_id})")
    with timer() as t_embed:
        chunks = segment_transcript(segments)

        total_duration = max((s["end"] for s in segments), default=0)
        full_transcript = " ".join(seg.get("text", "").strip() for seg in segments)
        save_media_file(
            media_id=media_id,
            filename=f"eval_{media_id}",
            file_type="video",
            duration=total_duration,
            metadata={"source": "evals", "config": config_snapshot},
            full_transcript=full_transcript,
        )

        for chunk in chunks:
            context_text = combine_multimodal_context(
                [chunk], frame_analyses, chunk["start"], chunk["end"]
            )
            embedding = get_text_embedding(context_text)
            matched_descs = [
                f["description"]
                for f in frame_analyses
                if chunk["start"] <= f["timestamp"] <= chunk["end"]
            ]
            frame_desc = " | ".join(matched_descs) if matched_descs else None
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

    print(f"[embed] {len(chunks)}개 세그먼트 저장 완료 ({t_embed()}ms)")
    return media_id, t_embed()


# ── qa ──


def run_qa(
    media_id: str,
    questions: List[Dict],
    reference: Optional[str],
) -> Tuple[List[Dict], Dict[str, Any], int]:
    """QA 실행 + 메트릭 계산.

    Returns:
        (qa_results, metrics, latency_ms)
    """
    # lazy import: LLM 호출 모듈을 실행 시점까지 지연
    from app.chat_utils import get_answer_by_chat_model
    from app.evaluation_utils import (
        calculate_answer_relevance,
        calculate_groundedness,
        calculate_retrieval_precision,
        calculate_wer_cer,
    )
    from app.media_utils import get_text_embedding
    from app.retrieval_utils import retrieve_segments
    from app.supabase_utils import (
        get_media_by_id,
        get_media_segments,
    )

    print(f"[qa] {len(questions)}개 질문으로 QA 실행 중...")

    qa_results = []
    with timer() as t_qa_total:
        for i, q in enumerate(questions, 1):
            query = q["query"]
            with timer() as t_question:
                # 검색 + 선별 (rerank/threshold)
                query_embedding = get_text_embedding(query)
                all_candidates, accepted = retrieve_segments(
                    query, query_embedding, media_id
                )

                # 답변 생성
                answer, context_text = get_answer_by_chat_model(query, accepted)

                # 메트릭 수집
                relevance = calculate_answer_relevance(query, answer)
                groundedness = calculate_groundedness(answer, context_text)
                precision = calculate_retrieval_precision(accepted, query)

            qa_results.append(
                {
                    "test_id": q.get("test_id", f"T{i}"),
                    "test_type": q.get("test_type", ""),
                    "query": query,
                    "answer": answer,
                    "context_text": context_text,
                    "sources": [
                        {
                            "chunk_index": s.get("chunk_index"),
                            "similarity": s.get("similarity"),
                            "accepted": s.get("accepted"),
                            "text": s.get("text", "")[:200],
                        }
                        for s in all_candidates
                    ],
                    "metrics": {
                        "answer_relevance": relevance,
                        "groundedness": groundedness,
                        "retrieval_precision": precision,
                    },
                    "latency_ms": t_question(),
                }
            )
            print(
                f"  [{i}/{len(questions)}] AR={relevance:.2f} GR={groundedness:.2f} RP={precision:.2f} ({t_question()}ms)"
            )

    # WER + CER (reference가 있을 때만)
    wer_score = None
    cer_score = None
    if reference:
        media = get_media_by_id(media_id)
        full_transcript = media.get("full_transcript") if media else None
        if not full_transcript:
            # fallback: full_transcript 컬럼이 없는 기존 데이터
            segments = get_media_segments(media_id)
            full_transcript = " ".join(seg.get("text", "") for seg in segments)
        wer_score, cer_score = calculate_wer_cer(reference, full_transcript)
        print(f"[qa] WER={wer_score:.3f}  CER={cer_score:.3f}")

    # 메트릭 집계
    def avg(key):
        vals = [r["metrics"][key] for r in qa_results]
        return sum(vals) / len(vals) if vals else 0.0

    metrics = {
        "wer": wer_score,
        "cer": cer_score,
        "answer_relevance": round(avg("answer_relevance"), 4),
        "groundedness": round(avg("groundedness"), 4),
        "retrieval_precision": round(avg("retrieval_precision"), 4),
    }

    print(f"[qa] 완료 ({t_qa_total()}ms)")
    print(f"[qa] 메트릭: {metrics}")

    return qa_results, metrics, t_qa_total()
