"""Central configuration for the Pueblo Vivo brain.

Everything tunable lives here so experiments and the server share one source of
truth. Values can be overridden via environment variables (handy for swapping the
cognition model between a fast 3B and a higher-quality 7B/8B).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class LLMConfig:
    host: str = _env("OLLAMA_HOST", "http://localhost:11434")
    # Cognition model. Default to a small/fast model so it can coexist with the
    # Unity 3D render on an 8 GB GPU. Bump to qwen2.5:7b / llama3.1:8b for quality
    # in headless runs (no render competing for VRAM).
    chat_model: str = _env("PUEBLO_CHAT_MODEL", "llama3.2:3b")
    embed_model: str = _env("PUEBLO_EMBED_MODEL", "nomic-embed-text")
    request_timeout: float = float(_env("PUEBLO_LLM_TIMEOUT", "120"))
    max_retries: int = int(_env("PUEBLO_LLM_RETRIES", "2"))
    temperature: float = float(_env("PUEBLO_LLM_TEMP", "0.8"))


@dataclass(frozen=True)
class RetrievalConfig:
    # Weights for the recency / importance / relevance blend (paper uses 1/1/1).
    w_recency: float = 1.0
    w_importance: float = 1.0
    w_relevance: float = 1.0
    # Recency decay applied per simulated tick since last access.
    recency_decay: float = 0.995
    top_k: int = 10


@dataclass(frozen=True)
class ReflectionConfig:
    # Reflect once the summed importance of memories since the last reflection
    # crosses this threshold.
    importance_threshold: float = 150.0
    # How many salient questions to derive per reflection cycle.
    num_questions: int = 3
    # Memories retrieved per question when synthesising insights.
    retrieve_per_question: int = 15


@dataclass(frozen=True)
class TimeConfig:
    minutes_per_tick: int = 10
    day_start_hour: int = 7  # agents wake and plan their day at this hour
    day_end_hour: int = 23


@dataclass(frozen=True)
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    reflection: ReflectionConfig = field(default_factory=ReflectionConfig)
    time: TimeConfig = field(default_factory=TimeConfig)
    db_path: str = _env("PUEBLO_DB", ":memory:")


# A module-level default; callers may construct their own Config.
DEFAULT = Config()
