import os
from contextlib import contextmanager
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Config:
    # 공급자 설정: local(기본, 로컬 Ollama + faster-whisper) | openai(클라우드)
    provider: str = os.getenv("PROVIDER", "local").lower()

    # ── Ollama 설정 (PROVIDER=local 시 사용) ──
    ollama_base: str = os.getenv("OLLAMA_BASE", "http://localhost:11434")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.1")
    # moondream => llava 전환
    ollama_vision_model: str = os.getenv("OLLAMA_VISION_MODEL", "llava")

    # faster-whisper 모델 크기: tiny | base | small | medium | large-v3 | large-v3-turbo
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "large-v3-turbo")

    # ── OpenAI 설정 (PROVIDER=openai 시 사용) ──
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_embedding_model: str = os.getenv(
        "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
    )
    openai_chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    openai_vision_model: str = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
    openai_whisper_model: str = os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")

    # ── 임베딩 차원 ──
    _LOCAL_EMBED_DIMS: dict = {
        "nomic-embed-text": 768,
        "bge-m3": 1024,
    }

    @property
    def embedding_dim(self) -> int:
        if self.provider != "local":
            return 1536
        return self._LOCAL_EMBED_DIMS.get(self.ollama_embed_model, 768)

    # ── 파일 시스템 ──
    upload_dir: str = "app/uploads"
    frames_dir: str = "app/frames"
    allowed_media_extensions: set = {
        "mp4",
        "mov",
        "avi",
        "mkv",
        "mp3",
        "wav",
        "m4a",
        "webm",
    }

    # ── 실험 파라미터  ──
    frames_per_minute: int = 3  # 분당 키프레임 추출 수 — 비전 실험
    chunk_window_seconds: float = 20.0  # 청킹 윈도우 크기(초)
    chunk_overlap_seconds: float = 5.0  # 청킹 오버랩(초) — 경계 발화 잘림 방지
    search_threshold: float = 0.3  # 벡터 검색 유사도 임계값
    search_top_k: int = 3  # 검색 상위 결과 수

    # ── Cohere Rerank ──
    use_rerank: bool = os.getenv("USE_RERANK", "false").lower() == "true"
    cohere_api_key: str = os.getenv("COHERE_API_KEY", "")
    rerank_model: str = os.getenv("RERANK_MODEL", "rerank-multilingual-v3.0")
    rerank_top_n: int = 3  # rerank 후 최종 선별 개수
    search_pre_rerank_k: int = 15  # rerank 전 넓게 가져올 개수

    # ── Supabase ──
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")


CONFIG = Config()


# ── Stage Config 모델 ──
# config-규약: "파이프라인 단계별 설정을 Pydantic BaseModel로 분리한다"
# flat CONFIG가 단일 진실 공급원. Stage Config는 CONFIG의 파생 뷰.


class TranscriptionCfg(BaseModel):
    provider: str
    whisper_model_size: str   # local: faster-whisper 모델 크기
    openai_whisper_model: str  # openai: Whisper API 모델명
    openai_api_key: str = ""


class VisionCfg(BaseModel):
    provider: str
    frames_per_minute: int
    ollama_vision_model: str
    openai_vision_model: str
    ollama_base: str = ""
    openai_api_key: str = ""


class EmbeddingCfg(BaseModel):
    provider: str
    chunk_window_seconds: float
    chunk_overlap_seconds: float
    ollama_embed_model: str
    openai_embedding_model: str
    embedding_dim: int
    ollama_base: str = ""
    openai_api_key: str = ""


class RetrievalCfg(BaseModel):
    search_top_k: int
    search_threshold: float
    use_rerank: bool
    rerank_model: str
    rerank_top_n: int
    search_pre_rerank_k: int
    cohere_api_key: str = ""


class QACfg(BaseModel):
    provider: str
    ollama_chat_model: str
    openai_chat_model: str
    ollama_base: str = ""
    openai_api_key: str = ""


class JudgeCfg(BaseModel):
    """1급 시민 — QACfg와 독립. Sprint 3 exp-06에서 judge/chat 동일 모델 편향 발견."""
    provider: str
    ollama_chat_model: str
    openai_chat_model: str
    ollama_base: str = ""
    openai_api_key: str = ""


class PipelineConfig(BaseModel):
    transcription: TranscriptionCfg
    vision: VisionCfg
    embedding: EmbeddingCfg
    retrieval: RetrievalCfg
    qa: QACfg
    judge: JudgeCfg


# Stage Config 필드명 → flat CONFIG 속성명 매핑
# override_config(vision={"frames_per_minute": 6}) 형태로 사용한다.
_STAGE_FIELD_MAP: dict[str, dict[str, str]] = {
    "transcription": {
        "provider": "provider",
        "whisper_model_size": "whisper_model_size",
        "openai_whisper_model": "openai_whisper_model",
    },
    "vision": {
        "provider": "provider",
        "frames_per_minute": "frames_per_minute",
        "ollama_vision_model": "ollama_vision_model",
        "openai_vision_model": "openai_vision_model",
    },
    "embedding": {
        "provider": "provider",
        "chunk_window_seconds": "chunk_window_seconds",
        "chunk_overlap_seconds": "chunk_overlap_seconds",
        "ollama_embed_model": "ollama_embed_model",
        "openai_embedding_model": "openai_embedding_model",
    },
    "retrieval": {
        "search_top_k": "search_top_k",
        "search_threshold": "search_threshold",
        "use_rerank": "use_rerank",
        "rerank_model": "rerank_model",
        "rerank_top_n": "rerank_top_n",
        "search_pre_rerank_k": "search_pre_rerank_k",
    },
    "qa": {
        "provider": "provider",
        "ollama_chat_model": "ollama_chat_model",
        "openai_chat_model": "openai_chat_model",
    },
    "judge": {
        "provider": "provider",
        "ollama_chat_model": "ollama_chat_model",
        "openai_chat_model": "openai_chat_model",
    },
}


@contextmanager
def override_config(**stage_overrides):
    """flat CONFIG 속성을 일시적으로 덮어쓰고 블록 종료 시 자동 복원한다.

    Usage:
        with override_config(vision={"frames_per_minute": 6}):
            run_experiment(...)
        # 블록 종료 시 frames_per_minute 자동 복원

    Args:
        **stage_overrides: stage 이름 → {필드명: 값} dict.
            stage 이름은 _STAGE_FIELD_MAP의 키와 동일해야 한다.
    """
    saved: dict[str, object] = {}

    for stage, fields in stage_overrides.items():
        if stage not in _STAGE_FIELD_MAP:
            raise ValueError(f"알 수 없는 stage: {stage!r}. 가능한 값: {list(_STAGE_FIELD_MAP)}")
        for field, value in fields.items():
            config_attr = _STAGE_FIELD_MAP[stage].get(field)
            if config_attr is None:
                raise ValueError(f"stage={stage!r}에 알 수 없는 필드: {field!r}")
            if config_attr not in saved:
                saved[config_attr] = getattr(CONFIG, config_attr)
            setattr(CONFIG, config_attr, value)

    try:
        yield
    finally:
        for attr, original in saved.items():
            setattr(CONFIG, attr, original)


def get_stage_config() -> PipelineConfig:
    """flat CONFIG에서 stage별 config를 빌드한다.

    호출 시점에 CONFIG를 읽으므로 override_config() 블록 안에서도 올바른 값을 반환한다.
    """
    return PipelineConfig(
        transcription=TranscriptionCfg(
            provider=CONFIG.provider,
            whisper_model_size=CONFIG.whisper_model_size,
            openai_whisper_model=CONFIG.openai_whisper_model,
            openai_api_key=CONFIG.openai_api_key,
        ),
        vision=VisionCfg(
            provider=CONFIG.provider,
            frames_per_minute=CONFIG.frames_per_minute,
            ollama_vision_model=CONFIG.ollama_vision_model,
            openai_vision_model=CONFIG.openai_vision_model,
            ollama_base=CONFIG.ollama_base,
            openai_api_key=CONFIG.openai_api_key,
        ),
        embedding=EmbeddingCfg(
            provider=CONFIG.provider,
            chunk_window_seconds=CONFIG.chunk_window_seconds,
            chunk_overlap_seconds=CONFIG.chunk_overlap_seconds,
            ollama_embed_model=CONFIG.ollama_embed_model,
            openai_embedding_model=CONFIG.openai_embedding_model,
            embedding_dim=CONFIG.embedding_dim,
            ollama_base=CONFIG.ollama_base,
            openai_api_key=CONFIG.openai_api_key,
        ),
        retrieval=RetrievalCfg(
            search_top_k=CONFIG.search_top_k,
            search_threshold=CONFIG.search_threshold,
            use_rerank=CONFIG.use_rerank,
            rerank_model=CONFIG.rerank_model,
            rerank_top_n=CONFIG.rerank_top_n,
            search_pre_rerank_k=CONFIG.search_pre_rerank_k,
            cohere_api_key=CONFIG.cohere_api_key,
        ),
        qa=QACfg(
            provider=CONFIG.provider,
            ollama_chat_model=CONFIG.ollama_chat_model,
            openai_chat_model=CONFIG.openai_chat_model,
            ollama_base=CONFIG.ollama_base,
            openai_api_key=CONFIG.openai_api_key,
        ),
        judge=JudgeCfg(
            provider=CONFIG.provider,
            ollama_chat_model=CONFIG.ollama_chat_model,
            openai_chat_model=CONFIG.openai_chat_model,
            ollama_base=CONFIG.ollama_base,
            openai_api_key=CONFIG.openai_api_key,
        ),
    )


# OpenAI 사용 시 필수 키 검증
if CONFIG.provider == "openai" and not CONFIG.openai_api_key:
    raise ValueError(
        "PROVIDER=openai로 설정했지만 OPENAI_API_KEY가 설정되지 않았습니다."
    )

# 디렉토리 생성
for _dir in (CONFIG.upload_dir, CONFIG.frames_dir):
    if not os.path.exists(_dir):
        os.makedirs(_dir)

# 시작 시 config 출력
if CONFIG.provider == "local":
    _models = f"""  Chat Model           : {CONFIG.ollama_chat_model}
  Vision Model         : {CONFIG.ollama_vision_model}
  Embed Model          : {CONFIG.ollama_embed_model}
  Whisper Size         : {CONFIG.whisper_model_size}
  Ollama Base          : {CONFIG.ollama_base}"""
else:
    _models = f"""  Chat Model           : {CONFIG.openai_chat_model}
  Vision Model         : {CONFIG.openai_vision_model}
  Embed Model          : {CONFIG.openai_embedding_model}
  Whisper Model        : {CONFIG.openai_whisper_model}"""

print(
    f"""
[config] ──────────────────────────────
  Provider             : {CONFIG.provider}
{_models}
  ─ Search / Chunking ─
  Embedding Dim        : {CONFIG.embedding_dim}
  Frames Per Minute    : {CONFIG.frames_per_minute}
  Chunk Window (sec)   : {CONFIG.chunk_window_seconds}
  Chunk Overlap (sec)  : {CONFIG.chunk_overlap_seconds}
  Search Threshold     : {CONFIG.search_threshold}
  Search Top-K         : {CONFIG.search_top_k}
  ─ Rerank ─
  Use Rerank           : {CONFIG.use_rerank}
  Rerank Model         : {CONFIG.rerank_model if CONFIG.use_rerank else "(disabled)"}
  Rerank Top-N         : {CONFIG.rerank_top_n if CONFIG.use_rerank else "(disabled)"}
  Pre-Rerank K         : {CONFIG.search_pre_rerank_k if CONFIG.use_rerank else "(disabled)"}
────────────────────────────────────────
"""
)
