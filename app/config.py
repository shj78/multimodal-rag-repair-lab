import os
from contextlib import contextmanager
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Config:
    # ── 공유: API 키 / 접속 정보 ──
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    ollama_base: str = os.getenv("OLLAMA_BASE", "http://localhost:11434")

    # ── Transcription ──
    transcribe_provider: str = os.getenv("TRANSCRIBE_PROVIDER", "local").lower()
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "large-v3-turbo")
    openai_whisper_model: str = os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")

    # ── Vision ──
    vision_provider: str = os.getenv("VISION_PROVIDER", "local").lower()
    ollama_vision_model: str = os.getenv("OLLAMA_VISION_MODEL", "llava")
    openai_vision_model: str = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
    frames_per_minute: int = 3

    # ── Embedding ──
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    openai_embedding_model: str = os.getenv(
        "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
    )
    chunk_window_seconds: float = 20.0
    chunk_overlap_seconds: float = 5.0

    _EMBED_DIMS: dict = {
        "nomic-embed-text": 768,
        "bge-m3": 1024,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
    }

    @property
    def embedding_dim(self) -> int:
        override = os.getenv("EMBEDDING_DIM")
        if override:
            return int(override)
        active_model = (
            self.openai_embedding_model
            if self.embedding_provider == "openai"
            else self.ollama_embed_model
        )
        return self._EMBED_DIMS.get(active_model, 768)

    # ── QA (Chat) ──
    chat_provider: str = os.getenv("CHAT_PROVIDER", "local").lower()
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.1")
    openai_chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

    # ── Judge ──
    judge_provider: str = os.getenv("JUDGE_PROVIDER", "local").lower()

    # ── Retrieval ──
    search_threshold: float = 0.3
    search_top_k: int = 3

    # ── Rerank ──
    use_rerank: bool = os.getenv("USE_RERANK", "false").lower() == "true"
    cohere_api_key: str = os.getenv("COHERE_API_KEY", "")
    rerank_model: str = os.getenv("RERANK_MODEL", "rerank-multilingual-v3.0")
    rerank_top_n: int = 3
    search_pre_rerank_k: int = 15

    # ── Supabase ──
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")

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


CONFIG = Config()


# ── Stage Config 모델 ──
# config-규약: "파이프라인 단계별 설정을 Pydantic BaseModel로 분리한다"
# flat CONFIG가 단일 진실 공급원. Stage Config는 CONFIG의 파생 뷰.


class TranscriptionCfg(BaseModel):
    provider: str
    whisper_model_size: str  # local: faster-whisper 모델 크기
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
        "provider": "transcribe_provider",
        "whisper_model_size": "whisper_model_size",
        "openai_whisper_model": "openai_whisper_model",
    },
    "vision": {
        "provider": "vision_provider",
        "frames_per_minute": "frames_per_minute",
        "ollama_vision_model": "ollama_vision_model",
        "openai_vision_model": "openai_vision_model",
    },
    "embedding": {
        "provider": "embedding_provider",
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
        "provider": "chat_provider",
        "ollama_chat_model": "ollama_chat_model",
        "openai_chat_model": "openai_chat_model",
    },
    "judge": {
        "provider": "judge_provider",
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
            raise ValueError(
                f"알 수 없는 stage: {stage!r}. 가능한 값: {list(_STAGE_FIELD_MAP)}"
            )
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
            provider=CONFIG.transcribe_provider,
            whisper_model_size=CONFIG.whisper_model_size,
            openai_whisper_model=CONFIG.openai_whisper_model,
            openai_api_key=CONFIG.openai_api_key,
        ),
        vision=VisionCfg(
            provider=CONFIG.vision_provider,
            frames_per_minute=CONFIG.frames_per_minute,
            ollama_vision_model=CONFIG.ollama_vision_model,
            openai_vision_model=CONFIG.openai_vision_model,
            ollama_base=CONFIG.ollama_base,
            openai_api_key=CONFIG.openai_api_key,
        ),
        embedding=EmbeddingCfg(
            provider=CONFIG.embedding_provider,
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
            provider=CONFIG.chat_provider,
            ollama_chat_model=CONFIG.ollama_chat_model,
            openai_chat_model=CONFIG.openai_chat_model,
            ollama_base=CONFIG.ollama_base,
            openai_api_key=CONFIG.openai_api_key,
        ),
        judge=JudgeCfg(
            provider=CONFIG.judge_provider,
            ollama_chat_model=CONFIG.ollama_chat_model,
            openai_chat_model=CONFIG.openai_chat_model,
            ollama_base=CONFIG.ollama_base,
            openai_api_key=CONFIG.openai_api_key,
        ),
    )


# OpenAI 사용 시 필수 키 검증 — 역할별 provider 중 하나라도 openai면 키 필요
_openai_providers = [
    (name, getattr(CONFIG, attr))
    for name, attr in [
        ("transcription", "transcribe_provider"),
        ("vision", "vision_provider"),
        ("embedding", "embedding_provider"),
        ("qa", "chat_provider"),
        ("judge", "judge_provider"),
    ]
    if getattr(CONFIG, attr) == "openai"
]
if _openai_providers and not CONFIG.openai_api_key:
    _names = ", ".join(name for name, _ in _openai_providers)
    raise ValueError(
        f"{_names} provider가 openai인데 OPENAI_API_KEY가 설정되지 않았습니다."
    )

# 디렉토리 생성
for _dir in (CONFIG.upload_dir, CONFIG.frames_dir):
    if not os.path.exists(_dir):
        os.makedirs(_dir)

# 시작 시 config 출력
_cfg = get_stage_config()
print(
    f"""
[config] ──────────────────────────────
  ─ Providers ─
  Transcription        : {_cfg.transcription.provider}
  Vision               : {_cfg.vision.provider}
  Embedding            : {_cfg.embedding.provider}
  QA (Chat)            : {_cfg.qa.provider}
  Judge                : {_cfg.judge.provider}
  ─ Models ─
  Transcription        : {_cfg.transcription.openai_whisper_model if _cfg.transcription.provider == "openai" else _cfg.transcription.whisper_model_size}
  Vision               : {_cfg.vision.openai_vision_model if _cfg.vision.provider == "openai" else _cfg.vision.ollama_vision_model}
  Embedding            : {_cfg.embedding.openai_embedding_model if _cfg.embedding.provider == "openai" else _cfg.embedding.ollama_embed_model}
  Chat                 : {_cfg.qa.openai_chat_model if _cfg.qa.provider == "openai" else _cfg.qa.ollama_chat_model}
  ─ Search / Chunking ─
  Embedding Dim        : {_cfg.embedding.embedding_dim}
  Frames Per Minute    : {_cfg.vision.frames_per_minute}
  Chunk Window (sec)   : {_cfg.embedding.chunk_window_seconds}
  Chunk Overlap (sec)  : {_cfg.embedding.chunk_overlap_seconds}
  Search Threshold     : {_cfg.retrieval.search_threshold}
  Search Top-K         : {_cfg.retrieval.search_top_k}
  ─ Rerank ─
  Use Rerank           : {_cfg.retrieval.use_rerank}
  Rerank Model         : {_cfg.retrieval.rerank_model if _cfg.retrieval.use_rerank else "(disabled)"}
  Rerank Top-N         : {_cfg.retrieval.rerank_top_n if _cfg.retrieval.use_rerank else "(disabled)"}
  Pre-Rerank K         : {_cfg.retrieval.search_pre_rerank_k if _cfg.retrieval.use_rerank else "(disabled)"}
────────────────────────────────────────
"""
)
del _cfg
