"""
Config 클래스 회귀 테스트.

Phase 1에서 Stage Config 도입, Phase 5에서 provider 분리 시 기존 동작이 보존되는지 검증한다.
"""

import pytest


class TestConfig:
    """flat Config 클래스의 기본 동작을 검증한다."""

    def test_config_instantiation(self):
        from app.config import Config

        cfg = Config()
        assert hasattr(cfg, "provider")
        assert hasattr(cfg, "embedding_dim")

    def test_embedding_dim_local_nomic(self):
        from app.config import Config

        cfg = Config()
        cfg.provider = "local"
        cfg.ollama_embed_model = "nomic-embed-text"
        assert cfg.embedding_dim == 768

    def test_embedding_dim_local_bge_m3(self):
        from app.config import Config

        cfg = Config()
        cfg.provider = "local"
        cfg.ollama_embed_model = "bge-m3"
        assert cfg.embedding_dim == 1024

    def test_embedding_dim_openai(self):
        from app.config import Config

        cfg = Config()
        cfg.provider = "openai"
        assert cfg.embedding_dim == 1536

    def test_default_chunking_params(self):
        from app.config import Config

        cfg = Config()
        assert cfg.chunk_window_seconds == 20.0
        assert cfg.chunk_overlap_seconds == 5.0

    def test_default_search_params(self):
        from app.config import Config

        cfg = Config()
        assert cfg.search_threshold == 0.3
        assert cfg.search_top_k == 3
