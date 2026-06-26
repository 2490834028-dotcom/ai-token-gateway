"""
语义缓存模块（Semantic Cache）

基于向量相似度的请求缓存层，对语义相近的 API 请求返回缓存结果，
减少重复调用上游 API 的次数，降低延迟和 Token 消耗。

工作原理：
1. 将请求的 messages 内容提取并生成语义向量（embedding）
2. 在 Redis 中查找相似度高于阈值的历史请求
3. 命中则直接返回缓存的响应；未命中则调用上游 API 并缓存结果

使用方式：
    cache = SemanticCache(redis_url="redis://localhost:6379", threshold=0.92)
    cached = await cache.lookup(messages)
    if cached is None:
        response = await call_upstream_api(messages)
        await cache.store(messages, response)
    else:
        response = cached
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目数据结构"""

    cache_key: str
    response: dict[str, Any]
    created_at: float
    hit_count: int = 0
    similarity: float = 1.0


@dataclass
class CacheStats:
    """缓存统计数据"""

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_similarity_on_hit: float = 0.0

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests


class SemanticCache:
    """
    基于语义相似度的请求缓存。

    Parameters
    ----------
    redis_url : str
        Redis 连接地址
    threshold : float
        相似度阈值，取值 [0, 1]，高于此值视为命中缓存，默认 0.92
    ttl : int
        缓存条目过期时间（秒），默认 3600（1小时）
    max_entries : int
        单个 prefix 下最大缓存条目数，默认 10000
    embedding_dim : int
        语义向量维度，默认 384（与 all-MiniLM-L6-v2 对齐）
    key_prefix : str
        Redis key 前缀，默认 "semantic_cache:"
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        threshold: float = 0.92,
        ttl: int = 3600,
        max_entries: int = 10000,
        embedding_dim: int = 384,
        key_prefix: str = "semantic_cache:",
    ) -> None:
        self.redis_url = redis_url
        self.threshold = threshold
        self.ttl = ttl
        self.max_entries = max_entries
        self.embedding_dim = embedding_dim
        self.key_prefix = key_prefix

        self._redis: redis.Redis | None = None
        self._stats = CacheStats()
        self._vector_cache: dict[str, np.ndarray] = {}

    async def connect(self) -> None:
        """建立 Redis 连接"""
        self._redis = redis.from_url(
            self.redis_url, decode_responses=False, max_connections=20
        )
        await self._redis.ping()
        logger.info("SemanticCache connected to Redis: %s", self.redis_url)

    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None

    # ------------------------------------------------------------------
    # 核心接口
    # ------------------------------------------------------------------

    async def lookup(self, messages: list[dict[str, str]]) -> dict[str, Any] | None:
        """
        查询缓存。

        Parameters
        ----------
        messages : list[dict]
            OpenAI 格式的 messages 列表

        Returns
        -------
        dict | None
            命中时返回缓存的 response，未命中返回 None
        """
        self._stats.total_requests += 1

        query_embedding = self._compute_embedding(messages)
        query_key = self._make_content_hash(messages)

        # 先检查精确匹配
        exact_match = await self._redis_get(query_key)
        if exact_match is not None:
            self._record_hit(1.0)
            return exact_match

        # 语义相似度搜索
        best_match, best_similarity = await self._similarity_search(
            query_embedding, query_key
        )

        if best_match is not None and best_similarity >= self.threshold:
            self._record_hit(best_similarity)
            logger.info(
                "Cache HIT (similarity=%.4f, threshold=%.4f)",
                best_similarity,
                self.threshold,
            )
            return best_match

        self._stats.cache_misses += 1
        logger.debug("Cache MISS (best_similarity=%.4f)", best_similarity)
        return None

    async def store(
        self, messages: list[dict[str, str]], response: dict[str, Any]
    ) -> None:
        """
        存储请求响应到缓存。

        Parameters
        ----------
        messages : list[dict]
            OpenAI 格式的 messages 列表
        response : dict
            上游 API 返回的完整响应体
        """
        content_hash = self._make_content_hash(messages)
        embedding = self._compute_embedding(messages)

        entry = {
            "response": json.dumps(response, ensure_ascii=False),
            "embedding": embedding.tobytes().hex(),
            "created_at": time.time(),
            "hit_count": 0,
        }

        await self._redis_set(content_hash, entry)
        await self._enforce_size_limit()

        logger.debug("Cached response for key=%s", content_hash[:12])

    async def invalidate(self, messages: list[dict[str, str]]) -> bool:
        """使指定请求的缓存失效"""
        content_hash = self._make_content_hash(messages)
        deleted = await self._redis_delete(content_hash)
        return deleted > 0

    async def clear(self) -> int:
        """清空所有语义缓存，返回删除条目数"""
        pattern = f"{self.key_prefix}*"
        keys = []
        async for key in self._redis.scan_iter(match=pattern, count=500):
            keys.append(key)
        if keys:
            return await self._redis.delete(*keys)
        return 0

    @property
    def stats(self) -> CacheStats:
        """返回当前缓存统计信息"""
        return self._stats

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _compute_embedding(self, messages: list[dict[str, str]]) -> np.ndarray:
        """
        计算 messages 的语义向量。

        使用简化的 TF-IDF 加权哈希方案生成固定维度向量，
        生产环境可替换为 sentence-transformers 等模型。
        """
        # 提取所有文本内容
        text = " ".join(
            msg.get("content", "")
            for msg in messages
            if isinstance(msg.get("content"), str)
        )

        # 简单的哈希向量方案（用于演示；生产环境替换为真实 embedding 模型）
        words = text.lower().split()
        vector = np.zeros(self.embedding_dim, dtype=np.float32)

        for i, word in enumerate(words):
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            idx = h % self.embedding_dim
            sign = 1 if (h // self.embedding_dim) % 2 == 0 else -1
            vector[idx] += sign / (1 + i * 0.01)  # 位置衰减

        # L2 归一化
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector

    def _make_content_hash(self, messages: list[dict[str, str]]) -> str:
        """生成消息内容的确定性哈希"""
        canonical = json.dumps(messages, sort_keys=True, ensure_ascii=False)
        return f"{self.key_prefix}hash:{hashlib.sha256(canonical.encode()).hexdigest()}"

    async def _similarity_search(
        self, query_embedding: np.ndarray, exclude_key: str
    ) -> tuple[dict[str, Any] | None, float]:
        """在缓存中查找最相似的条目"""
        pattern = f"{self.key_prefix}hash:*"
        best_entry = None
        best_similarity = -1.0

        async for raw_key in self._redis.scan_iter(match=pattern, count=200):
            key = raw_key if isinstance(raw_key, str) else raw_key.decode()

            if key == exclude_key:
                continue

            raw_data = await self._redis_get_raw(key)
            if raw_data is None or "embedding" not in raw_data:
                continue

            stored_vec = np.frombuffer(
                bytes.fromhex(raw_data["embedding"]), dtype=np.float32
            )
            similarity = float(np.dot(query_embedding, stored_vec))

            if similarity > best_similarity:
                best_similarity = similarity
                best_entry = json.loads(raw_data["response"])

        return best_entry, best_similarity

    def _record_hit(self, similarity: float) -> None:
        """记录缓存命中"""
        self._stats.cache_hits += 1
        n = self._stats.cache_hits
        old_avg = self._stats.avg_similarity_on_hit
        self._stats.avg_similarity_on_hit = old_avg + (similarity - old_avg) / n

    # ------------------------------------------------------------------
    # Redis 操作封装
    # ------------------------------------------------------------------

    async def _redis_get(self, key: str) -> dict[str, Any] | None:
        raw = await self._redis_get_raw(key)
        if raw is not None:
            return json.loads(raw["response"])
        return None

    async def _redis_get_raw(self, key: str) -> dict | None:
        data = await self._redis.hgetall(key)
        if not data:
            return None
        return {
            k.decode() if isinstance(k, bytes) else k: (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in data.items()
        }

    async def _redis_set(self, key: str, entry: dict) -> None:
        await self._redis.hset(key, mapping=entry)
        await self._redis.expire(key, self.ttl)

    async def _redis_delete(self, key: str) -> int:
        return await self._redis.delete(key)

    async def _enforce_size_limit(self) -> None:
        """当缓存条目数超过上限时，淘汰最旧的条目"""
        pattern = f"{self.key_prefix}hash:*"
        keys = []
        async for key in self._redis.scan_iter(match=pattern, count=500):
            keys.append(key if isinstance(key, str) else key.decode())

        if len(keys) <= self.max_entries:
            return

        # 按创建时间排序，删除最旧的
        entries_with_time = []
        for key in keys:
            raw = await self._redis_get_raw(key)
            if raw and "created_at" in raw:
                entries_with_time.append((key, float(raw["created_at"])))

        entries_with_time.sort(key=lambda x: x[1])
        to_delete = len(entries_with_time) - self.max_entries

        for key, _ in entries_with_time[:to_delete]:
            await self._redis.delete(key)

        logger.info("Evicted %d stale cache entries", to_delete)
