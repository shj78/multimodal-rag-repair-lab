"""
supabase_utils.py — Supabase 데이터베이스 유틸리티

[TODO]
구현 순서: save_media_file → save_segment → get_all_media → search_similar_segments → get_media_segments
※ update_media_status는 이미 완성된 코드입니다. 건드리지 마세요.

⚠️  supabase 2.x 주의사항:
    이 프로젝트는 supabase==2.3.0을 사용합니다.
    이전 스프린트(1.0.3)와 클라이언트 API가 일부 변경되었습니다.
    이전 스프린트 코드를 직접 복사하면 오류가 발생할 수 있습니다.
    - 응답 구조: response.data (동일), response.error → 예외 처리 방식 변경
    - RPC 호출 패턴: .rpc("함수명", {파라미터}) → 동일
"""

from supabase import create_client, Client
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config import CONFIG


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
) -> Dict:
    """
    media_files 테이블에 미디어 파일 정보를 저장합니다.

    Args:
        media_id (str): 미디어 UUID
        filename (str): 원본 파일명
        file_type (str): "audio" | "video"
        duration (float): 재생 시간(초)
        metadata (Dict): 추가 메타데이터 (JSONB)
        full_transcript (str | None): 원본 전사 텍스트 (WER/CER 계산용)

    Returns:
        Dict: 저장된 레코드
    """
    row = {
        "id": media_id,
        "filename": filename,
        "file_type": file_type,
        "duration_seconds": duration,
        "status": "processing",
        "metadata": metadata or {},
        "created_at": datetime.utcnow().isoformat(),
    }
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
    """
    [완성 코드] media_files 테이블의 상태를 업데이트합니다. (오케스트레이터에서 호출)
    """
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
    """
    [TODO] media_segments 테이블에 세그먼트를 저장합니다.

    요구사항:
    1. README.md의 DB 스키마(media_segments 테이블)를 확인하세요.
    2. embedding은 List[float] 형태 그대로 전달하면 pgvector가 처리합니다.
    3. frame_description은 오디오 전용 파일이면 None으로 저장합니다.

    Args:
        media_id (str): 상위 media_files의 id
        chunk_index (int): 청크 순서 인덱스
        text (str): 세그먼트 전사 텍스트
        start_time (float): 시작 시간(초)
        end_time (float): 종료 시간(초)
        embedding (List[float]): 임베딩 벡터
        frame_description (str | None): 해당 구간 프레임 설명

    Returns:
        Dict: 저장된 레코드
    """

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


def search_similar_segments(
    query_embedding: List[float],
    media_id: str,
    limit: int = CONFIG.search_top_k,
    threshold: float = CONFIG.search_threshold,
    skip_threshold: bool = False,
) -> List[Dict[str, Any]]:
    """
    [TODO] 쿼리 벡터와 유사한 세그먼트를 코사인 유사도로 검색합니다.

    요구사항:
    1. README.md의 DB 스키마에서 생성한 match_segments RPC 함수를 호출하세요.
       - 파라미터: query_embedding, match_count, p_media_id
    2. 반환된 결과 중 similarity가 threshold 이상인 것만 필터링하세요.

    힌트:
        response = supabase.rpc(
            "match_segments",
            {
                "query_embedding": query_embedding,
                "match_count": limit,
                "p_media_id": media_id,
            },
        ).execute()
        results = response.data or []
        return [r for r in results if r.get("similarity", 0) >= threshold]

    Args:
        query_embedding (List[float]): 쿼리 임베딩 벡터
        media_id (str): 검색 대상 미디어 ID
        limit (int): 반환할 최대 결과 수
        threshold (float): 유사도 임계값

    Returns:
        List[Dict]: 유사 세그먼트 목록
    """
    # ---------------------------------------------------------
    # [TODO] 벡터 유사도 검색 로직 작성
    # ---------------------------------------------------------

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
    """
    [TODO] media_files 테이블에서 전체 미디어 목록을 조회합니다.

    요구사항:
    1. 최신순(created_at DESC)으로 정렬하여 반환하세요.

    Returns:
        List[Dict]: 미디어 파일 목록
    """
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
    """
    [TODO] 특정 미디어의 모든 세그먼트를 chunk_index 순서로 반환합니다.

    Args:
        media_id (str): 조회할 미디어 ID

    Returns:
        List[Dict]: 세그먼트 목록 (chunk_index ASC)
    """
    # ---------------------------------------------------------
    # [TODO] 세그먼트 조회 로직 작성
    # ---------------------------------------------------------
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
