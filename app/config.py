import os
from dotenv import load_dotenv

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
