from supabase import create_client, Client
from typing import List, Dict, Any, Optional
from datetime import datetime

from langsmith import traceable

from app.config import CONFIG, RetrievalCfg, get_stage_config


class SupabaseOperationError(Exception):
    """Supabase DB 작업 실패 시 발생하는 예외"""

    pass


def _handle_supabase_error(e: Exception, operation: str) -> None:
    """Supabase 예외를 분석하여 명확한 메시지로 변환합니다."""
    msg = str(e).lower()
    if "invalid" in msg or "401" in msg or "apikey" in msg or "unauthorized" in msg:
        raise SupabaseOperationError(
            f"Supabase 인증 실패 — SUPABASE_KEY를 확인하세요. (작업: {operation})"
        ) from e
    raise SupabaseOperationError(f"Supabase DB 작업 실패 ({operation}): {e}") from e


if not CONFIG.supabase_url or not CONFIG.supabase_key:
    raise ValueError("SUPABASE_URL과 SUPABASE_KEY가 설정되어 있어야 합니다.")

try:
    supabase: Client = create_client(CONFIG.supabase_url, CONFIG.supabase_key)
except Exception as e:
    supabase = None  # type: ignore[assignment]
    print(f"[supabase] 클라이언트 초기화 실패: {e}")


def _ensure_client() -> Client:
    """Supabase 클라이언트가 유효한지 확인합니다."""
    if supabase is None:
        raise SupabaseOperationError(
            "Supabase 연결 실패 — SUPABASE_KEY가 유효하지 않습니다. 환경변수를 확인하세요."
        )
    return supabase


def save_media_file(
    media_id: str,
    filename: str,
    file_type: str,
    duration: float,
    metadata: Optional[Dict] = None,
    full_transcript: Optional[str] = None,
    file_path: Optional[str] = None,
) -> Dict:
    row = {
        "id": media_id,
        "filename": filename,
        "file_type": file_type,
        "duration_seconds": duration,
        "status": "processing",
        "metadata": metadata or {},
        "created_at": datetime.utcnow().isoformat(),
    }
    if file_path is not None:
        row["file_path"] = file_path
    if full_transcript is not None:
        row["full_transcript"] = full_transcript

    try:
        response = _ensure_client().table("media_files").insert(row).execute()
    except SupabaseOperationError:
        raise
    except Exception as e:
        _handle_supabase_error(e, "save_media_file")

    return response.data


def get_media_by_id(media_id: str) -> Optional[Dict]:
    """media_files에서 특정 미디어를 조회합니다."""
    try:
        response = (
            _ensure_client()
            .table("media_files")
            .select("*")
            .eq("id", media_id)
            .single()
            .execute()
        )
    except SupabaseOperationError:
        raise
    except Exception as e:
        _handle_supabase_error(e, "get_media_by_id")
    return response.data


def update_media_status(
    media_id: str, status: str, segment_count: Optional[int] = None
) -> None:
    data: Dict[str, Any] = {
        "status": status,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if segment_count is not None:
        data["segment_count"] = segment_count
    try:
        _ensure_client().table("media_files").update(data).eq("id", media_id).execute()
    except SupabaseOperationError:
        raise
    except Exception as e:
        _handle_supabase_error(e, "update_media_status")


def save_segment(
    media_id: str,
    chunk_index: int,
    text: str,
    start_time: float,
    end_time: float,
    embedding: List[float],
    frame_description: Optional[str] = None,
) -> Dict:
    try:
        response = (
            _ensure_client()
            .table("media_segments")
            .insert(
                {
                    "media_id": media_id,
                    "chunk_index": chunk_index,
                    "text": text,
                    "start_time": start_time,
                    "end_time": end_time,
                    "embedding": embedding,
                    "frame_description": frame_description,
                }
            )
            .execute()
        )
    except SupabaseOperationError:
        raise
    except Exception as e:
        _handle_supabase_error(e, "save_segment")

    return response.data


@traceable(name="qa.2_vector_search", run_type="retriever")
def search_similar_segments(
    query_embedding: List[float],
    media_id: str,
    cfg: RetrievalCfg | None = None,
    skip_threshold: bool = False,
) -> List[Dict[str, Any]]:
    cfg = cfg or get_stage_config().retrieval
    limit = cfg.search_top_k
    threshold = cfg.search_threshold
    try:
        response = (
            _ensure_client()
            .rpc(
                "match_segments",
                {
                    "query_embedding": query_embedding,
                    "match_count": limit,
                    "p_media_id": media_id,
                },
            )
            .execute()
        )
    except SupabaseOperationError:
        raise
    except Exception as e:
        _handle_supabase_error(e, "search_similar_segments")
    results = response.data or []

    if skip_threshold:
        return results

    return [r for r in results if r.get("similarity", 0) >= threshold]


def get_all_media() -> List[Dict[str, Any]]:
    try:
        response = (
            _ensure_client()
            .table("media_files")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
    except SupabaseOperationError:
        raise
    except Exception as e:
        _handle_supabase_error(e, "get_all_media")

    return response.data or []


def get_media_segments(media_id: str) -> List[Dict[str, Any]]:
    try:
        response = (
            _ensure_client()
            .table("media_segments")
            .select("*")
            .eq("media_id", media_id)
            .order("chunk_index")
            .execute()
        )
    except SupabaseOperationError:
        raise
    except Exception as e:
        _handle_supabase_error(e, "get_media_segments")

    return response.data or []
