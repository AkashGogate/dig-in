"""Versioned menu vectors: local lexical baseline and opt-in semantic provider.

Never call a network provider while holding Restaurant.lock. Voice uses only the
local suggestion index; explicit search may use the configured remote provider.
"""

from __future__ import annotations

import hashlib
import math
import os
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.mvp.menu import MenuDocument, normalize


class EmbeddingError(ValueError):
    """Sanitized provider/configuration failure; never includes credentials/input."""


class EmbeddingProvider(Protocol):
    name: str
    semantic: bool

    def encode(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbeddings:
    """Deterministic feature hashing, not a trained semantic/AI model."""

    name = "local-hash-v1-512"
    semantic = False

    def encode(self, texts):
        result = []
        for text in texts:
            words = normalize(text).split()
            features = Counter(f"word:{word}" for word in words)
            for word in words:
                padded = f"^{word}$"
                features.update(
                    f"char:{padded[n : n + 3]}" for n in range(len(padded) - 2)
                )
            vector = [0.0] * 512
            for feature, count in features.items():
                digest = hashlib.sha256(feature.encode()).digest()
                vector[int.from_bytes(digest[:4], "big") % 512] += count
            result.append(vector)
        return result


class OpenAIEmbeddings:
    """Explicitly enabled paid adapter. No default key discovery or live tests."""

    semantic = True

    def __init__(self, api_key: str, model: str, *, transport=None):
        if not api_key or not model:
            raise EmbeddingError("OpenAI embeddings require an explicit key and model")
        self._api_key, self.model, self._transport = api_key, model, transport
        self.name = f"openai:{model}"

    def encode(self, texts):
        vectors = []
        try:
            with httpx.Client(timeout=15, transport=self._transport) as client:
                for start in range(0, len(texts), 32):
                    batch = texts[start : start + 32]
                    response = client.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json={
                            "model": self.model,
                            "input": batch,
                            "encoding_format": "float",
                        },
                    )
                    response.raise_for_status()
                    rows = response.json()["data"]
                    if sorted(row["index"] for row in rows) != list(range(len(batch))):
                        raise ValueError("Incomplete/duplicate embedding indices")
                    vectors.extend(
                        row["embedding"]
                        for row in sorted(rows, key=lambda r: r["index"])
                    )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise EmbeddingError(
                "Embedding provider failed; active menu is unchanged"
            ) from exc
        return vectors


def provider_from_env():
    mode = os.environ.get("DIG_IN_EMBEDDINGS_MODE", "local")
    if mode == "local":
        return LocalEmbeddings()
    if mode == "openai":
        return OpenAIEmbeddings(
            os.environ.get("DIG_IN_EMBEDDINGS_API_KEY", ""),
            os.environ.get("DIG_IN_EMBEDDINGS_MODEL", ""),
        )
    raise EmbeddingError("DIG_IN_EMBEDDINGS_MODE must be local or openai")


def menu_revision(menu: MenuDocument) -> str:
    import json

    canonical = json.dumps(
        menu.model_dump(mode="json"), sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _unit_vectors(rows, count, dimensions=None):
    try:
        if len(rows) != count:
            raise ValueError("Wrong row count")
        result = []
        for row in rows:
            if not row or (dimensions is not None and len(row) != dimensions):
                raise ValueError("Wrong dimension")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in row):
                raise ValueError("Non-numeric vector")
            if not all(math.isfinite(v) for v in row):
                raise ValueError("Non-finite vector")
            norm = math.sqrt(sum(v * v for v in row))
            if norm == 0 or not math.isfinite(norm):
                raise ValueError("Invalid vector norm")
            dimensions = len(row)
            result.append(tuple(v / norm for v in row))
        return tuple(result)
    except (ValueError, TypeError, OverflowError) as exc:
        raise EmbeddingError("Embedding provider returned invalid vectors") from exc


@dataclass(frozen=True)
class MenuIndex:
    revision: str
    item_ids: tuple[str, ...]
    vectors: tuple[tuple[float, ...], ...]
    local_vectors: tuple[tuple[float, ...], ...]
    provider: EmbeddingProvider

    @classmethod
    def build(cls, menu, provider):
        # Customer descriptions are search text, never recipes/dietary guarantees.
        texts = [
            " ".join(
                filter(
                    None, [item.name, *item.aliases, item.description, item.category]
                )
            )
            for item in menu.items
        ]
        local = _unit_vectors(LocalEmbeddings().encode(texts), len(texts))
        vectors = (
            local
            if type(provider) is LocalEmbeddings
            else _unit_vectors(provider.encode(texts), len(texts))
        )
        return cls(
            menu_revision(menu),
            tuple(i.id for i in menu.items),
            vectors,
            local,
            provider,
        )

    def status(self):
        return {
            "menu_revision": self.revision,
            "provider": self.provider.name,
            "semantic": self.provider.semantic,
            "dimensions": len(self.vectors[0]),
            "item_count": len(self.item_ids),
            "candidate_only": True,
            "voice_suggestions": "local_only_no_network",
        }

    def search(self, text, limit=5, *, local=False):
        if not normalize(text):
            return []
        provider = LocalEmbeddings() if local else self.provider
        rows = self.local_vectors if local else self.vectors
        query = _unit_vectors(provider.encode([text]), 1, len(rows[0]))[0]
        scored = [
            {
                "menu_id": key,
                "score": sum(a * b for a, b in zip(query, vector, strict=True)),
            }
            for key, vector in zip(self.item_ids, rows, strict=True)
        ]
        # Scores are cosine similarity, never calibrated confidence/food identity.
        return sorted(
            (row for row in scored if row["score"] > 0),
            key=lambda row: (-row["score"], row["menu_id"]),
        )[:limit]

    def suggest_local(self, text):
        return [row["menu_id"] for row in self.search(text, 3, local=True)]
