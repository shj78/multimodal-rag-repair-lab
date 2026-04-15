"""
embedding.py — 텍스트 임베딩 (ingest + qa 공유 도메인)

임베딩은 ingest에서는 문서 청크를 벡터화하고, qa에서는 쿼리를 벡터화하는
양쪽 경계에 걸쳐 있어 특정 도메인 폴더에 속하지 않는다. 기능 단위 이름으로
루트에 독립시키되, /shared/ 같은 범용 서랍장은 만들지 않는다.
"""

import time
from typing import List

import requests
from langsmith import traceable

from .config import EmbeddingCfg, get_stage_config


@traceable(name="query_embedding", run_type="tool")
def get_text_embedding(text: str, cfg: EmbeddingCfg | None = None) -> List[float]:
    cfg = cfg or get_stage_config().embedding
    if cfg.provider == "openai":
        from openai import OpenAI, RateLimitError

        client = OpenAI(api_key=cfg.openai_api_key)
        for attempt in range(5):
            try:
                resp = client.embeddings.create(
                    model=cfg.openai_embedding_model,
                    input=text,
                    dimensions=cfg.embedding_dim,
                )
                return resp.data[0].embedding
            except RateLimitError:
                wait = min(2**attempt, 10)
                print(
                    f"[embedding] Rate limit hit, retrying in {wait}s... ({attempt + 1}/5)"
                )
                time.sleep(wait)
        raise RuntimeError("OpenAI embedding rate limit: 5회 재시도 후에도 실패")
    else:
        response = requests.post(
            f"{cfg.ollama_base}/api/embeddings",
            json={"model": cfg.ollama_embed_model, "prompt": text},
        )
        return response.json()["embedding"]
