# ============================================================
# MediaFlow AI Agent — 메인 애플리케이션
# ============================================================

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Body
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Request
import os
import requests
from uuid import uuid4
from typing import Dict, List, Any
from datetime import datetime
from openai import AuthenticationError as OpenAIAuthError

from .config import CONFIG, get_stage_config
from .diagnostics import get_config_snapshot, timer, StageTimer
from .transcription_utils import extract_audio_from_video, transcribe_audio
from .vision_utils import extract_key_frames, analyze_frame_with_vision_model
from .media_utils import (
    segment_transcript,
    get_text_embedding,
    combine_multimodal_context,
)
from .supabase_utils import (
    save_media_file,
    save_segment,
    get_all_media,
    get_media_by_id,
    get_media_segments,
    update_media_status,
    SupabaseOperationError,
)
from .evaluation_utils import run_full_evaluation
from .chat_utils import get_answer_by_chat_model
from .retrieval_utils import retrieve_segments
from .correction_utils import correct_transcription_with_vision

app = FastAPI(title="MediaFlow AI Agent")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ────────────────────────────────────────
# [완성 코드] Job State Machine
# pending → transcribing → analyzing_frames → embedding → ready | failed
# ────────────────────────────────────────
job_store: Dict[str, Dict[str, Any]] = {}


def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in CONFIG.allowed_media_extensions
    )


def is_video_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {
        "mp4",
        "mov",
        "avi",
        "mkv",
        "webm",
    }


# ────────────────────────────────────────
# [완성 코드] 백그라운드 처리 오케스트레이터
# Job State: pending → transcribing → analyzing_frames → embedding → ready | failed
# 여러분이 구현한 함수들이 이 함수 내부에서 호출됩니다.
# ────────────────────────────────────────
async def process_media_background(
    job_id: str, media_id: str, file_path: str, filename: str
):
    try:
        is_video = is_video_file(filename)
        st = StageTimer()

        # 시작 시 config 스냅샷 저장 (처리 중 config 변경 대비)
        job_store[job_id]["config"] = get_config_snapshot()

        # ── 1단계: 오디오 추출 (비디오인 경우) ──
        with st.measure("audio_extract"):
            if is_video:
                audio_path = os.path.join(CONFIG.upload_dir, f"{media_id}_audio.wav")
                extract_audio_from_video(file_path, audio_path)
            else:
                audio_path = file_path

        # ── 2단계: 전사 ──
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

        # ── 3단계: 키 프레임 분석 (비디오인 경우) ──
        frame_analyses: List[Dict[str, Any]] = []
        frame_count = 0
        if is_video:
            job_store[job_id]["status"] = "analyzing_frames"
            with st.measure("vision_total"):
                frames_dir = os.path.join(CONFIG.frames_dir, media_id)
                os.makedirs(frames_dir, exist_ok=True)
                frames = extract_key_frames(
                    file_path, frames_dir, frames_per_minute=get_stage_config().vision.frames_per_minute
                )
                frame_count = len(frames)
                for frame in frames:
                    description = analyze_frame_with_vision_model(
                        frame["frame_path"], frame["timestamp"]
                    )
                    frame_analyses.append(
                        {"timestamp": frame["timestamp"], "description": description}
                    )

        # ── 3.5단계: Vision-guided 전사 교정 ──
        segments = correct_transcription_with_vision(segments, frame_analyses)

        # ── 4단계: 세그먼트 청킹 + 임베딩 + 저장 ──
        job_store[job_id]["status"] = "embedding"
        with st.measure("embed_save"):
            chunks = segment_transcript(segments)

            for chunk in chunks:
                context_text = combine_multimodal_context(
                    [chunk], frame_analyses, chunk["start"], chunk["end"]
                )

                embedding = get_text_embedding(context_text)
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


# ────────────────────────────────────────
# 라우트
# ────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def root_page(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/media/{media_id}/file")
async def serve_media_file(media_id: str):
    media = get_media_by_id(media_id)
    if not media or not media.get("file_path"):
        raise HTTPException(status_code=404, detail="미디어 파일을 찾을 수 없습니다.")
    file_path = media["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일이 서버에 존재하지 않습니다.")
    return FileResponse(file_path)


# [완성 코드] 건강 체크
@app.get("/health")
async def health_check():
    cfg = get_stage_config()
    providers = {
        "transcription": cfg.transcription.provider,
        "vision": cfg.vision.provider,
        "embedding": cfg.embedding.provider,
        "qa": cfg.qa.provider,
        "judge": cfg.judge.provider,
    }
    components: Dict[str, Any] = {"status": "ok", "providers": providers}

    has_local = any(p == "local" for p in providers.values())
    if has_local:
        try:
            resp = requests.get(f"{CONFIG.ollama_base}/api/tags", timeout=3)
            components["ollama"] = "ok" if resp.status_code == 200 else "error"
        except Exception:
            components["ollama"] = "unreachable"

    return components


# [완성 코드] Job 상태 폴링
@app.get("/media/jobs/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="job not found")
    return job_store[job_id]


# [완성 코드] 미디어 업로드 — 파이프라인 오케스트레이션은 process_media_background()가 처리
@app.post("/media/upload")
async def upload_media(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    미디어 파일(오디오/비디오)을 업로드하고 백그라운드 처리를 시작합니다.

    반환: job_id — 클라이언트는 GET /media/jobs/{job_id}로 상태를 폴링합니다.
    여러분이 구현한 함수들이 process_media_background() 내부에서 자동으로 호출됩니다.
    """
    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 허용: {CONFIG.allowed_media_extensions}",
        )

    media_id = str(uuid4())
    job_id = str(uuid4())
    ext = file.filename.rsplit(".", 1)[1].lower()
    file_path = os.path.join(CONFIG.upload_dir, f"{media_id}.{ext}")

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    job_store[job_id] = {
        "status": "pending",
        "media_id": media_id,
        "filename": file.filename,
        "created_at": datetime.utcnow().isoformat(),
    }

    background_tasks.add_task(
        process_media_background, job_id, media_id, file_path, file.filename
    )

    return {"job_id": job_id, "media_id": media_id, "status": "pending"}


# 미디어 목록 조회
@app.get("/media/")
async def list_media():
    result = get_all_media()

    return {"media": result}


# Q&A
@app.post("/qa")
async def question_answering(body: Dict[str, Any] = Body(...)):
    if "query" not in body or "media_id" not in body:
        raise HTTPException(status_code=400, detail="query와 media_id가 필요합니다.")

    query = body["query"]
    media_id = body["media_id"]

    latency_ms: Dict[str, int] = {}

    # 1. 임베딩
    with timer() as t_embed:
        query_embedding = get_text_embedding(query)
    latency_ms["embedding"] = t_embed()

    # 2. 검색 + 선별 (rerank/threshold)
    with timer() as t_retrieval:
        all_segments, accepted_segments = retrieve_segments(
            query, query_embedding, media_id
        )
    latency_ms["retrieval"] = t_retrieval()

    # 4. 답변 생성
    with timer() as t_gen:
        answer, context_text = get_answer_by_chat_model(query, accepted_segments)
    latency_ms["generation"] = t_gen()
    latency_ms["total"] = (
        latency_ms["embedding"] + latency_ms["retrieval"] + latency_ms["generation"]
    )

    return {
        "answer": answer,
        "context_text": context_text,
        "sources": all_segments,
        "media_id": media_id,
        "config": get_config_snapshot(),
        "latency_ms": latency_ms,
    }


# 세그먼트 목록 조회 (UI 전사 패널에서 사용)
@app.get("/media/{media_id}/segments")
async def get_segments(media_id: str):
    return {"segments": get_media_segments(media_id), "media_id": media_id}


# 요약
@app.post("/media/{media_id}/summary")
async def summarize_media(media_id: str):
    segments = get_media_segments(media_id)

    full_text = "\n".join(seg["text"] for seg in segments)

    messages = [
        {
            "role": "system",
            "content": "당신은 인터뷰 내용을 요약하는 전문가입니다.",
        },
        {
            "role": "user",
            "content": f"아래 인터뷰 전사 내용을 핵심 위주로 요약하세요:\n\n{full_text}",
        },
    ]

    qa_cfg = get_stage_config().qa
    if qa_cfg.provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=qa_cfg.openai_api_key)
        resp = client.chat.completions.create(
            model=qa_cfg.openai_chat_model,
            messages=messages,
        )
        summary = resp.choices[0].message.content
    else:
        resp = requests.post(
            f"{qa_cfg.ollama_base}/api/chat",
            json={
                "model": qa_cfg.ollama_chat_model,
                "messages": messages,
                "stream": False,
            },
        )
        summary = resp.json()["message"]["content"]

    return {"summary": summary, "media_id": media_id}


# 평가
@app.get("/media/{media_id}/evaluate")
async def evaluate_media(
    media_id: str, test_questions: str = "", reference_transcript: str = ""
):
    questions = [q.strip() for q in test_questions.split(",") if q.strip()]
    if len(questions) < 1:
        raise HTTPException(
            status_code=400, detail="평가할 질문이 최소 1개 필요합니다."
        )
    result = run_full_evaluation(media_id, questions, reference_transcript or None)

    return {
        "metrics": result["metrics"],
        "qa_results": result["qa_results"],
        "question_count": result["question_count"],
        "config": get_config_snapshot(),
        "media_id": media_id,
    }
