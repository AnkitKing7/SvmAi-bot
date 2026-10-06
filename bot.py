#!/usr/bin/env python3
"""
SVM AI — Ultimate Autonomous Discord AI Agent
Made by AnkitCoder

Primary AI Engine: LocalAI
"""

from __future__ import annotations

import asyncio
import aiofiles
import aiosqlite
import base64
import hashlib
import html
import io
import json
import logging
import mimetypes
import os
import platform
import random
import re
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
import uuid
import zipfile
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)
from urllib.parse import urljoin, urlparse

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Constants & Branding
# ---------------------------------------------------------------------------
BRAND = "SVM AI"
AUTHOR = "AnkitCoder"
VERSION = "1.0.0"
LOCALAI_DEFAULT = "http://127.0.0.1:8080"
MAX_DISCORD_MSG = 1900
MAX_EMBED_DESC = 4000
SAFE_SHELL_CMDS = {
    "python", "python3", "node", "npm", "npx", "git", "pip", "pip3",
    "ls", "pwd", "echo", "cat", "head", "tail", "wc", "file", "which",
    "uname", "df", "du", "free", "uptime", "date",
}
DANGEROUS_PATTERNS = re.compile(
    r"\b(rm\s+-rf|dd\s+if=|mkfs|shutdown|reboot|iptables|chmod\s+777|"
    r"curl\s+.*\|\s*bash|wget\s+.*\|\s*bash|systemctl\s+(stop|disable)|"
    r"docker\s+rm|:>\s*/|truncate\s+-s\s+0)\b",
    re.I,
)
SSRF_BLOCKED = re.compile(
    r"^(127\.|10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|169\.254\.|"
    r"0\.|::1|localhost|metadata\.google|169\.254\.169\.254)",
    re.I,
)
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|private[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{36,}"),
    re.compile(r"xox[baprs]-[0-9a-zA-Z-]{10,}"),
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging(log_dir: str = "./logs", level: str = "INFO") -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / "svm_ai.log"
    logger = logging.getLogger("svmai")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


log = setup_logging()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass
class Config:
    discord_token: str = ""
    admin_ids: Set[int] = field(default_factory=set)
    prefix: str = "!"
    message_ai_enabled: bool = False

    localai_url: str = LOCALAI_DEFAULT
    localai_api_key: str = ""
    localai_model: str = ""
    localai_general_model: str = ""
    localai_coding_model: str = ""
    localai_reasoning_model: str = ""
    localai_vision_model: str = ""
    localai_image_model: str = ""

    fallback_ai_url: str = ""
    fallback_ai_key: str = ""
    fallback_ai_model: str = ""

    search_provider: str = ""
    search_api_key: str = ""
    search_custom_url: str = ""

    image_provider: str = ""
    image_api_url: str = ""
    image_api_key: str = ""
    image_model: str = ""

    workspace_dir: Path = Path("./workspace")
    data_dir: Path = Path("./data")
    log_dir: Path = Path("./logs")

    max_repair_loops: int = 5
    request_timeout: int = 180
    max_context_messages: int = 20
    max_message_length: int = 1900
    rate_limit_enabled: bool = True
    user_cooldown: float = 2.0
    admin_bypass_rate_limit: bool = True
    log_level: str = "INFO"

    @classmethod
    def load(cls) -> "Config":
        load_dotenv()
        admin_raw = os.getenv("ADMIN_IDS", "")
        admin_ids: Set[int] = set()
        for part in admin_raw.replace(" ", "").split(","):
            if part.isdigit():
                admin_ids.add(int(part))
        cfg = cls(
            discord_token=os.getenv("DISCORD_TOKEN", "").strip(),
            admin_ids=admin_ids,
            prefix=os.getenv("PREFIX", "!").strip() or "!",
            message_ai_enabled=os.getenv("MESSAGE_AI_ENABLED", "false").lower() == "true",
            localai_url=os.getenv("LOCALAI_URL", LOCALAI_DEFAULT).rstrip("/"),
            localai_api_key=os.getenv("LOCALAI_API_KEY", ""),
            localai_model=os.getenv("LOCALAI_MODEL", ""),
            localai_general_model=os.getenv("LOCALAI_GENERAL_MODEL", ""),
            localai_coding_model=os.getenv("LOCALAI_CODING_MODEL", ""),
            localai_reasoning_model=os.getenv("LOCALAI_REASONING_MODEL", ""),
            localai_vision_model=os.getenv("LOCALAI_VISION_MODEL", ""),
            localai_image_model=os.getenv("LOCALAI_IMAGE_MODEL", ""),
            fallback_ai_url=os.getenv("FALLBACK_AI_URL", ""),
            fallback_ai_key=os.getenv("FALLBACK_AI_KEY", ""),
            fallback_ai_model=os.getenv("FALLBACK_AI_MODEL", ""),
            search_provider=os.getenv("SEARCH_PROVIDER", "").lower().strip(),
            search_api_key=os.getenv("SEARCH_API_KEY", ""),
            search_custom_url=os.getenv("SEARCH_CUSTOM_URL", ""),
            image_provider=os.getenv("IMAGE_PROVIDER", "").lower().strip(),
            image_api_url=os.getenv("IMAGE_API_URL", ""),
            image_api_key=os.getenv("IMAGE_API_KEY", ""),
            image_model=os.getenv("IMAGE_MODEL", ""),
            workspace_dir=Path(os.getenv("WORKSPACE_DIR", "./workspace")),
            data_dir=Path(os.getenv("DATA_DIR", "./data")),
            log_dir=Path(os.getenv("LOG_DIR", "./logs")),
            max_repair_loops=int(os.getenv("MAX_REPAIR_LOOPS", "5")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "180")),
            max_context_messages=int(os.getenv("MAX_CONTEXT_MESSAGES", "20")),
            max_message_length=int(os.getenv("MAX_MESSAGE_LENGTH", "1900")),
            rate_limit_enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
            user_cooldown=float(os.getenv("USER_COOLDOWN", "2")),
            admin_bypass_rate_limit=os.getenv("ADMIN_BYPASS_RATE_LIMIT", "true").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
        cfg.workspace_dir.mkdir(parents=True, exist_ok=True)
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        cfg.log_dir.mkdir(parents=True, exist_ok=True)
        return cfg

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def mask_secrets(text: str) -> str:
    for pat in SECRET_PATTERNS:
        text = pat.sub(lambda m: m.group(0)[:8] + "***MASKED***", text)
    return text


def smart_chunk(text: str, limit: int = MAX_DISCORD_MSG) -> List[str]:
    if not text:
        return [""]
    if len(text) <= limit:
        return [text]
    chunks: List[str] = []
    current = ""
    in_fence = False
    fence_lang = ""
    lines = text.split("\n")
    for line in lines:
        if line.strip().startswith("```"):
            if not in_fence:
                in_fence = True
                fence_lang = line.strip()[3:]
            else:
                in_fence = False
        candidate = current + ("\n" if current else "") + line
        if len(candidate) > limit and current:
            if in_fence:
                chunks.append(current + "\n```")
                current = f"```{fence_lang}\n" + line
            else:
                chunks.append(current)
                current = line
        else:
            current = candidate
    if current:
        if in_fence and not current.rstrip().endswith("```"):
            current += "\n```"
        chunks.append(current)
    return chunks or [""]


def safe_path(base: Path, *parts: str) -> Path:
    """Resolve path under base, blocking traversal."""
    target = base.joinpath(*parts).resolve()
    base_resolved = base.resolve()
    if not str(target).startswith(str(base_resolved)):
        raise PermissionError("Path traversal blocked")
    return target


def is_ssrf_blocked(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return True
        if SSRF_BLOCKED.match(host):
            return True
        # Resolve and check private IPs
        try:
            infos = socket.getaddrinfo(host, None)
            for info in infos:
                ip = info[4][0]
                if SSRF_BLOCKED.match(ip):
                    return True
        except socket.gaierror:
            pass
        return False
    except Exception:
        return True


def detect_intent(text: str) -> str:
    t = text.lower().strip()
    if any(k in t for k in ("generate image", "draw ", "create image", "make an image", "/image")):
        return "IMAGE"
    if any(k in t for k in ("analyze this image", "what is in this", "describe the image", "vision")):
        return "VISION"
    if any(k in t for k in ("github.com/", "analyze repo", "github analysis", "/github")):
        return "GITHUB"
    if any(k in t for k in ("seo ", "seo analysis", "keyword research", "/seo")):
        return "SEO"
    if any(k in t for k in ("debug", "traceback", "error:", "exception", "fix this error")):
        return "DEBUG"
    if any(k in t for k in ("create a", "build a", "write a", "generate code", "make a website", "project")):
        return "CODING"
    if any(k in t for k in ("research", "latest", "current", "2026", "news", "what is new", "search for")):
        return "RESEARCH"
    if any(k in t for k in ("deep dive", "in-depth", "thorough analysis")):
        return "DEEP"
    return "CHAT"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
class Database:
    def __init__(self, path: Path):
        self.path = path
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._init_schema()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def _init_schema(self) -> None:
        assert self._db
        await self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_seen TEXT,
                last_seen TEXT,
                total_requests INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER,
                channel_id INTEGER,
                created_at TEXT,
                updated_at TEXT,
                summary TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                user_id INTEGER,
                name TEXT,
                path TEXT,
                created_at TEXT,
                updated_at TEXT,
                status TEXT DEFAULT 'active'
            );
            CREATE TABLE IF NOT EXISTS project_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT,
                rel_path TEXT,
                size INTEGER,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                command TEXT,
                tokens_est INTEGER DEFAULT 0,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                user_id INTEGER,
                status TEXT,
                progress TEXT,
                result TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id);
            """
        )
        await self._db.commit()

    async def ensure_user(self, user_id: int, username: str) -> None:
        assert self._db
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            """
            INSERT INTO users (user_id, username, first_seen, last_seen, total_requests)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                last_seen=excluded.last_seen,
                total_requests=total_requests+1
            """,
            (user_id, username, now, now),
        )
        await self._db.commit()

    async def get_or_create_session(self, user_id: int, channel_id: int) -> str:
        assert self._db
        now = datetime.now(timezone.utc).isoformat()
        # Reuse recent session within 1 hour
        cur = await self._db.execute(
            """
            SELECT session_id FROM sessions
            WHERE user_id=? AND channel_id=? AND updated_at > datetime('now', '-1 hour')
            ORDER BY updated_at DESC LIMIT 1
            """,
            (user_id, channel_id),
        )
        row = await cur.fetchone()
        if row:
            await self._db.execute(
                "UPDATE sessions SET updated_at=? WHERE session_id=?",
                (now, row["session_id"]),
            )
            await self._db.commit()
            return row["session_id"]
        sid = str(uuid.uuid4())
        await self._db.execute(
            "INSERT INTO sessions (session_id, user_id, channel_id, created_at, updated_at) VALUES (?,?,?,?,?)",
            (sid, user_id, channel_id, now, now),
        )
        await self._db.commit()
        return sid

    async def add_message(self, session_id: str, user_id: int, role: str, content: str) -> None:
        assert self._db
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT INTO messages (session_id, user_id, role, content, created_at) VALUES (?,?,?,?,?)",
            (session_id, user_id, role, content[:50000], now),
        )
        await self._db.commit()

    async def get_recent_messages(self, session_id: str, limit: int = 20) -> List[Dict[str, str]]:
        assert self._db
        cur = await self._db.execute(
            """
            SELECT role, content FROM messages
            WHERE session_id=? ORDER BY id DESC LIMIT ?
            """,
            (session_id, limit),
        )
        rows = await cur.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    async def create_project(self, user_id: int, name: str, path: str) -> str:
        assert self._db
        pid = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT INTO projects (project_id, user_id, name, path, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (pid, user_id, name, path, now, now),
        )
        await self._db.commit()
        return pid

    async def list_projects(self, user_id: int) -> List[Dict]:
        assert self._db
        cur = await self._db.execute(
            "SELECT project_id, name, path, created_at, status FROM projects WHERE user_id=? AND status='active' ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_project(self, project_id: str, user_id: int) -> Optional[Dict]:
        assert self._db
        cur = await self._db.execute(
            "SELECT * FROM projects WHERE project_id=? AND user_id=?",
            (project_id, user_id),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def delete_project(self, project_id: str, user_id: int) -> bool:
        assert self._db
        await self._db.execute(
            "UPDATE projects SET status='deleted' WHERE project_id=? AND user_id=?",
            (project_id, user_id),
        )
        await self._db.commit()
        return True

    async def log_usage(self, user_id: int, command: str, tokens: int = 0) -> None:
        assert self._db
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT INTO usage (user_id, command, tokens_est, created_at) VALUES (?,?,?,?)",
            (user_id, command, tokens, now),
        )
        await self._db.commit()

    async def get_setting(self, key: str) -> Optional[str]:
        assert self._db
        cur = await self._db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        assert self._db
        await self._db.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await self._db.commit()


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
class RateLimiter:
    def __init__(self, cooldown: float = 2.0):
        self.cooldown = cooldown
        self._last: Dict[int, float] = {}

    def check(self, user_id: int, is_admin: bool = False, bypass: bool = False) -> Tuple[bool, float]:
        if is_admin and bypass:
            return True, 0.0
        now = time.monotonic()
        last = self._last.get(user_id, 0.0)
        remaining = self.cooldown - (now - last)
        if remaining > 0:
            return False, remaining
        self._last[user_id] = now
        return True, 0.0


# ---------------------------------------------------------------------------
# LocalAI Client
# ---------------------------------------------------------------------------
class LocalAIClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.base = cfg.localai_url.rstrip("/")
        self.api_key = cfg.localai_api_key
        self._session: Optional[aiohttp.ClientSession] = None
        self.available_models: List[str] = []
        self.healthy = False

    async def start(self) -> None:
        timeout = aiohttp.ClientTimeout(total=self.cfg.request_timeout)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        await self.refresh_models()

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def _get(self, path: str) -> Any:
        assert self._session
        url = f"{self.base}{path}"
        async with self._session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"LocalAI GET {path} → {resp.status}: {text[:200]}")
            return await resp.json()

    async def _post(self, path: str, payload: dict) -> Any:
        assert self._session
        url = f"{self.base}{path}"
        async with self._session.post(url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"LocalAI POST {path} → {resp.status}: {text[:300]}")
            return await resp.json()

    async def refresh_models(self) -> List[str]:
        try:
            data = await self._get("/v1/models")
            models = []
            if isinstance(data, dict) and "data" in data:
                models = [m.get("id", m.get("name", "")) for m in data["data"] if m]
            elif isinstance(data, list):
                models = [m.get("id", m.get("name", str(m))) for m in data]
            self.available_models = [m for m in models if m]
            self.healthy = True
            log.info("LocalAI models: %s", self.available_models)
        except Exception as e:
            self.healthy = False
            self.available_models = []
            log.warning("LocalAI model list failed: %s", e)
        return self.available_models

    def select_model(self, role: str = "GENERAL") -> str:
        role = role.upper()
        mapping = {
            "GENERAL": self.cfg.localai_general_model or self.cfg.localai_model,
            "CODING": self.cfg.localai_coding_model or self.cfg.localai_model,
            "REASONING": self.cfg.localai_reasoning_model or self.cfg.localai_model,
            "VISION": self.cfg.localai_vision_model or self.cfg.localai_model,
            "IMAGE": self.cfg.localai_image_model or self.cfg.localai_model,
        }
        preferred = mapping.get(role, self.cfg.localai_model)
        if preferred and (not self.available_models or preferred in self.available_models):
            return preferred
        if self.available_models:
            # Heuristic match
            keywords = {
                "CODING": ["code", "coder", "deepseek", "starcoder", "wizardcoder"],
                "REASONING": ["reason", "think", "qwen", "llama", "mistral", "phi"],
                "VISION": ["vision", "llava", "minicpm", "bakllava", "moondream"],
                "IMAGE": ["sd", "stable", "flux", "image", "diffusion"],
            }
            for kw in keywords.get(role, []):
                for m in self.available_models:
                    if kw in m.lower():
                        return m
            return self.available_models[0]
        return preferred or "gpt-4"

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        role: str = "GENERAL",
    ) -> str:
        model = model or self.select_model(role)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            data = await self._post("/v1/chat/completions", payload)
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError("Empty response from LocalAI")
            content = choices[0].get("message", {}).get("content") or choices[0].get("text", "")
            return (content or "").strip()
        except Exception as e:
            log.error("LocalAI chat error: %s", e)
            # Attempt fallback
            if self.cfg.fallback_ai_url:
                return await self._fallback_chat(messages, temperature, max_tokens)
            raise

    async def _fallback_chat(
        self, messages: List[Dict], temperature: float, max_tokens: int
    ) -> str:
        if not self.cfg.fallback_ai_url:
            raise RuntimeError("LocalAI unavailable and no fallback configured")
        headers = {"Content-Type": "application/json"}
        if self.cfg.fallback_ai_key:
            headers["Authorization"] = f"Bearer {self.cfg.fallback_ai_key}"
        payload = {
            "model": self.cfg.fallback_ai_model or "gpt-3.5-turbo",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        timeout = aiohttp.ClientTimeout(total=self.cfg.request_timeout)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as sess:
            async with sess.post(
                f"{self.cfg.fallback_ai_url.rstrip('/')}/v1/chat/completions",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Fallback AI error {resp.status}: {text[:200]}")
                data = await resp.json()
                return (data["choices"][0]["message"]["content"] or "").strip()

    async def vision(
        self, prompt: str, image_b64: str, mime: str = "image/png"
    ) -> str:
        model = self.select_model("VISION")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                ],
            }
        ]
        return await self.chat(messages, model=model, role="VISION", temperature=0.3)

    async def generate_image(self, prompt: str, size: str = "512x512") -> Optional[bytes]:
        model = self.select_model("IMAGE") or self.cfg.image_model
        # LocalAI image endpoint (OpenAI-compatible)
        payload = {
            "model": model or "stablediffusion",
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        }
        try:
            data = await self._post("/v1/images/generations", payload)
            items = data.get("data") or []
            if not items:
                return None
            b64 = items[0].get("b64_json")
            if b64:
                return base64.b64decode(b64)
            url = items[0].get("url")
            if url and self._session:
                async with self._session.get(url) as r:
                    if r.status == 200:
                        return await r.read()
        except Exception as e:
            log.warning("LocalAI image gen failed: %s", e)
        # External image provider
        if self.cfg.image_api_url and self.cfg.image_api_key:
            return await self._external_image(prompt)
        return None

    async def _external_image(self, prompt: str) -> Optional[bytes]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.cfg.image_api_key}",
        }
        payload = {
            "model": self.cfg.image_model or "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
            "response_format": "b64_json",
        }
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as sess:
            async with sess.post(self.cfg.image_api_url, json=payload) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                b64 = (data.get("data") or [{}])[0].get("b64_json")
                return base64.b64decode(b64) if b64 else None

    async def health(self) -> Dict[str, Any]:
        try:
            await self.refresh_models()
            return {
                "healthy": self.healthy,
                "url": self.base,
                "models": self.available_models,
                "selected": {
                    "general": self.select_model("GENERAL"),
                    "coding": self.select_model("CODING"),
                    "reasoning": self.select_model("REASONING"),
                    "vision": self.select_model("VISION"),
                    "image": self.select_model("IMAGE"),
                },
            }
        except Exception as e:
            return {"healthy": False, "error": str(e), "url": self.base}


# ---------------------------------------------------------------------------
# Search Engine
# ---------------------------------------------------------------------------
class SearchEngine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.provider = cfg.search_provider
        self.api_key = cfg.search_api_key

    @property
    def available(self) -> bool:
        return bool(self.provider and self.api_key) or bool(self.cfg.search_custom_url)

    async def search(self, query: str, num: int = 5) -> List[Dict[str, str]]:
        if not self.available:
            return []
        try:
            if self.provider == "brave":
                return await self._brave(query, num)
            if self.provider == "tavily":
                return await self._tavily(query, num)
            if self.provider == "serper":
                return await self._serper(query, num)
            if self.provider in ("bing", "custom") or self.cfg.search_custom_url:
                return await self._custom(query, num)
            return []
        except Exception as e:
            log.error("Search error: %s", e)
            return []

    async def _brave(self, query: str, num: int) -> List[Dict[str, str]]:
        headers = {"Accept": "application/json", "X-Subscription-Token": self.api_key}
        params = {"q": query, "count": num}
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as sess:
            async with sess.get("https://api.search.brave.com/res/v1/web/search", params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                results = []
                for r in (data.get("web", {}).get("results") or [])[:num]:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("description", ""),
                    })
                return results

    async def _tavily(self, query: str, num: int) -> List[Dict[str, str]]:
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": num,
            "include_answer": False,
        }
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.post("https://api.tavily.com/search", json=payload) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", ""),
                    }
                    for r in (data.get("results") or [])[:num]
                ]

    async def _serper(self, query: str, num: int) -> List[Dict[str, str]]:
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {"q": query, "num": num}
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as sess:
            async with sess.post("https://google.serper.dev/search", json=payload) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("link", ""),
                        "snippet": r.get("snippet", ""),
                    }
                    for r in (data.get("organic") or [])[:num]
                ]

    async def _custom(self, query: str, num: int) -> List[Dict[str, str]]:
        url = self.cfg.search_custom_url or "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": self.api_key} if self.api_key else {}
        params = {"q": query, "count": num}
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as sess:
            async with sess.get(url, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                web = data.get("webPages", {}).get("value") or data.get("results") or []
                return [
                    {
                        "title": r.get("name", r.get("title", "")),
                        "url": r.get("url", r.get("link", "")),
                        "snippet": r.get("snippet", r.get("description", "")),
                    }
                    for r in web[:num]
                ]


# ---------------------------------------------------------------------------
# Web / URL tools
# ---------------------------------------------------------------------------
class WebTools:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    async def fetch_page(self, url: str, max_chars: int = 30000) -> Dict[str, Any]:
        if is_ssrf_blocked(url):
            return {"error": "SSRF protection: blocked internal/private URL", "url": url}
        try:
            timeout = aiohttp.ClientTimeout(total=25)
            headers = {
                "User-Agent": "SVM-AI/1.0 (+https://github.com/AnkitCoder/svm-ai; research bot)"
            }
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as sess:
                async with sess.get(url, allow_redirects=True, ssl=False) as resp:
                    status = resp.status
                    ctype = resp.headers.get("Content-Type", "")
                    text = await resp.text(errors="replace")
                    if len(text) > max_chars:
                        text = text[:max_chars] + "\n...[truncated]"
                    title = ""
                    description = ""
                    headings: List[str] = []
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(text, "lxml")
                        if soup.title:
                            title = soup.title.get_text(strip=True)
                        meta = soup.find("meta", attrs={"name": "description"}) or soup.find(
                            "meta", attrs={"property": "og:description"}
                        )
                        if meta and meta.get("content"):
                            description = meta["content"]
                        for tag in soup.find_all(["h1", "h2", "h3"]):
                            h = tag.get_text(strip=True)
                            if h:
                                headings.append(f"{tag.name.upper()}: {h}")
                        # Clean body text
                        for s in soup(["script", "style", "nav", "footer", "header"]):
                            s.decompose()
                        body = soup.get_text(separator="\n", strip=True)
                        body = re.sub(r"\n{3,}", "\n\n", body)[:max_chars]
                    except Exception:
                        body = text[:max_chars]
                    return {
                        "url": str(resp.url),
                        "status": status,
                        "content_type": ctype,
                        "title": title,
                        "description": description,
                        "headings": headings[:30],
                        "text": body,
                    }
        except Exception as e:
            return {"error": str(e), "url": url}

    async def check_url(self, url: str) -> Dict[str, Any]:
        if is_ssrf_blocked(url):
            return {"url": url, "ok": False, "error": "SSRF blocked"}
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.head(url, allow_redirects=True, ssl=False) as resp:
                    return {
                        "url": str(resp.url),
                        "status": resp.status,
                        "ok": 200 <= resp.status < 400,
                        "content_type": resp.headers.get("Content-Type", ""),
                    }
        except Exception as e:
            return {"url": url, "ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Workspace / File Engine
# ---------------------------------------------------------------------------
class Workspace:
    def __init__(self, base: Path):
        self.base = base
        self.base.mkdir(parents=True, exist_ok=True)

    def user_dir(self, user_id: int) -> Path:
        p = self.base / str(user_id)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def project_dir(self, user_id: int, project_id: str) -> Path:
        p = self.user_dir(user_id) / project_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def write_file(self, user_id: int, project_id: str, rel_path: str, content: str) -> Path:
        root = self.project_dir(user_id, project_id)
        target = safe_path(root, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def read_file(self, user_id: int, project_id: str, rel_path: str) -> str:
        root = self.project_dir(user_id, project_id)
        target = safe_path(root, rel_path)
        if not target.is_file():
            raise FileNotFoundError(rel_path)
        return target.read_text(encoding="utf-8", errors="replace")

    def list_files(self, user_id: int, project_id: str) -> List[str]:
        root = self.project_dir(user_id, project_id)
        files = []
        for p in root.rglob("*"):
            if p.is_file():
                files.append(str(p.relative_to(root)))
        return sorted(files)

    def delete_file(self, user_id: int, project_id: str, rel_path: str) -> None:
        root = self.project_dir(user_id, project_id)
        target = safe_path(root, rel_path)
        if target.is_file():
            target.unlink()

    def zip_project(self, user_id: int, project_id: str) -> Path:
        root = self.project_dir(user_id, project_id)
        zip_path = self.user_dir(user_id) / f"{project_id}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in root.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(root))
        return zip_path

    def safe_extract_zip(self, zip_bytes: bytes, dest: Path) -> List[str]:
        dest.mkdir(parents=True, exist_ok=True)
        extracted = []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for info in zf.infolist():
                name = info.filename
                if name.startswith("/") or ".." in name.split("/"):
                    continue  # zip-slip protection
                target = safe_path(dest, name)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted.append(name)
        return extracted


# ---------------------------------------------------------------------------
# Code Testing & Repair
# ---------------------------------------------------------------------------
class CodeTester:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    async def test_file(self, path: Path) -> Dict[str, Any]:
        suffix = path.suffix.lower()
        if suffix == ".py":
            return await self._test_python(path)
        if suffix == ".json":
            return self._test_json(path)
        if suffix in (".yaml", ".yml"):
            return self._test_yaml(path)
        if suffix in (".html", ".htm"):
            return self._test_html(path)
        if suffix in (".js", ".mjs", ".cjs"):
            return await self._test_js(path)
        if suffix == ".css":
            return {"ok": True, "message": "CSS static check skipped (no syntax errors detectable without browser)"}
        return {"ok": True, "message": f"No automated test for {suffix}"}

    async def _test_python(self, path: Path) -> Dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "py_compile", str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0:
                return {"ok": True, "message": "Python syntax OK"}
            return {"ok": False, "message": (stderr or stdout).decode(errors="replace")[:1500]}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def _test_json(self, path: Path) -> Dict[str, Any]:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            return {"ok": True, "message": "JSON valid"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def _test_yaml(self, path: Path) -> Dict[str, Any]:
        try:
            import yaml
            yaml.safe_load(path.read_text(encoding="utf-8"))
            return {"ok": True, "message": "YAML valid"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def _test_html(self, path: Path) -> Dict[str, Any]:
        try:
            from bs4 import BeautifulSoup
            content = path.read_text(encoding="utf-8", errors="replace")
            soup = BeautifulSoup(content, "lxml")
            issues = []
            if not soup.find("html"):
                issues.append("Missing <html> tag")
            if not soup.find("title"):
                issues.append("Missing <title>")
            return {"ok": len(issues) == 0, "message": "; ".join(issues) or "HTML structure OK"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    async def _test_js(self, path: Path) -> Dict[str, Any]:
        # Prefer node --check if available
        node = shutil.which("node")
        if node:
            try:
                proc = await asyncio.create_subprocess_exec(
                    node, "--check", str(path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
                if proc.returncode == 0:
                    return {"ok": True, "message": "JavaScript syntax OK"}
                return {"ok": False, "message": (stderr or stdout).decode(errors="replace")[:1500]}
            except Exception as e:
                return {"ok": False, "message": str(e)}
        return {"ok": True, "message": "Node not available — skipped JS check"}


# ---------------------------------------------------------------------------
# GitHub Analyzer
# ---------------------------------------------------------------------------
class GitHubAnalyzer:
    def __init__(self, cfg: Config, ai: LocalAIClient):
        self.cfg = cfg
        self.ai = ai

    def parse_url(self, url: str) -> Optional[Tuple[str, str]]:
        m = re.match(
            r"https?://(?:www\.)?github\.com/([^/]+)/([^/#?]+)",
            url.strip(),
        )
        if m:
            return m.group(1), m.group(2).rstrip(".git")
        return None

    async def analyze(self, url: str) -> str:
        parsed = self.parse_url(url)
        if not parsed:
            return "❌ Invalid GitHub repository URL. Expected: https://github.com/owner/repo"
        owner, repo = parsed
        api = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "SVM-AI"}
        timeout = aiohttp.ClientTimeout(total=40)
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as sess:
                async with sess.get(api) as resp:
                    if resp.status == 404:
                        return "❌ Repository not found or private."
                    if resp.status != 200:
                        return f"❌ GitHub API error: {resp.status}"
                    meta = await resp.json()

                # README
                readme_text = ""
                async with sess.get(f"{api}/readme") as r2:
                    if r2.status == 200:
                        rd = await r2.json()
                        content = rd.get("content", "")
                        if content:
                            readme_text = base64.b64decode(content).decode("utf-8", errors="replace")[:8000]

                # Languages
                langs = {}
                async with sess.get(f"{api}/languages") as r3:
                    if r3.status == 200:
                        langs = await r3.json()

                # Tree (shallow)
                tree_items = []
                default_branch = meta.get("default_branch", "main")
                async with sess.get(f"{api}/git/trees/{default_branch}?recursive=1") as r4:
                    if r4.status == 200:
                        tree = await r4.json()
                        for item in (tree.get("tree") or [])[:200]:
                            if item.get("type") == "blob":
                                tree_items.append(item["path"])

            summary = {
                "name": meta.get("full_name"),
                "description": meta.get("description"),
                "stars": meta.get("stargazers_count"),
                "forks": meta.get("forks_count"),
                "language": meta.get("language"),
                "license": (meta.get("license") or {}).get("spdx_id"),
                "created": meta.get("created_at"),
                "updated": meta.get("updated_at"),
                "topics": meta.get("topics"),
                "languages": langs,
                "file_count": len(tree_items),
                "sample_files": tree_items[:40],
                "readme_excerpt": readme_text[:4000],
            }

            prompt = (
                "You are a senior software architect performing a GitHub repository analysis.\n"
                "Analyze the following repository metadata and produce a clear, structured report covering:\n"
                "1. Overview\n2. Architecture & structure\n3. Languages & tech stack\n"
                "4. Potential security concerns (secrets, dependencies)\n"
                "5. Code quality observations\n6. Recommendations\n\n"
                f"Repository data:\n{json.dumps(summary, indent=2)[:12000]}"
            )
            report = await self.ai.chat(
                [{"role": "user", "content": prompt}],
                role="CODING",
                temperature=0.3,
            )
            header = (
                f"**Repository:** [{summary['name']}]({url})\n"
                f"**Stars:** {summary['stars']} · **Forks:** {summary['forks']} · "
                f"**Language:** {summary['language']}\n\n"
            )
            return header + report
        except Exception as e:
            log.exception("GitHub analysis failed")
            return f"❌ Analysis failed: {e}"


# ---------------------------------------------------------------------------
# SEO Analyzer
# ---------------------------------------------------------------------------
class SEOAnalyzer:
    def __init__(self, web: WebTools, ai: LocalAIClient, search: SearchEngine):
        self.web = web
        self.ai = ai
        self.search = search

    async def analyze_url(self, url: str) -> str:
        page = await self.web.fetch_page(url)
        if page.get("error"):
            return f"❌ Could not fetch URL: {page['error']}"
        data = {
            "url": page.get("url"),
            "status": page.get("status"),
            "title": page.get("title"),
            "description": page.get("description"),
            "headings": page.get("headings", [])[:20],
            "text_sample": (page.get("text") or "")[:5000],
        }
        prompt = (
            "You are an expert SEO auditor. Analyze this webpage data and produce a professional SEO report with:\n"
            "- SEO Score (0-100 estimate)\n- Search Intent\n- Title & Meta evaluation\n"
            "- Heading structure\n- Content quality signals\n- Technical recommendations\n"
            "- On-page recommendations\n- Priority action list\n\n"
            f"Page data:\n{json.dumps(data, indent=2)}"
        )
        report = await self.ai.chat(
            [{"role": "user", "content": prompt}],
            role="REASONING",
            temperature=0.4,
        )
        return f"**SEO Analysis for** {url}\n\n{report}"

    async def analyze_topic(self, topic: str) -> str:
        results = []
        if self.search.available:
            results = await self.search.search(f"{topic} SEO keywords", num=6)
            results += await self.search.search(f"{topic} search intent", num=4)
        context = json.dumps(results, indent=2)[:6000] if results else "No live search available."
        prompt = (
            "You are an SEO strategist. For the topic below produce:\n"
            "1. Primary & secondary keywords\n2. Search intent analysis\n"
            "3. Content outline (H1-H3)\n4. Title & meta description suggestions\n"
            "5. Semantic / LSI keywords\n6. Content gap ideas\n7. Schema recommendations\n\n"
            f"Topic: {topic}\n\nSearch context:\n{context}"
        )
        return await self.ai.chat(
            [{"role": "user", "content": prompt}],
            role="REASONING",
            temperature=0.5,
        )


# ---------------------------------------------------------------------------
# Coding Agent
# ---------------------------------------------------------------------------
class CodingAgent:
    def __init__(
        self,
        cfg: Config,
        ai: LocalAIClient,
        workspace: Workspace,
        tester: CodeTester,
        db: Database,
    ):
        self.cfg = cfg
        self.ai = ai
        self.ws = workspace
        self.tester = tester
        self.db = db

    async def run(
        self,
        user_id: int,
        prompt: str,
        progress_cb: Optional[Callable[[str], Coroutine]] = None,
    ) -> Tuple[str, Optional[Path]]:
        async def prog(msg: str) -> None:
            if progress_cb:
                await progress_cb(msg)

        await prog("🧠 Understanding request...")
        plan_prompt = (
            "You are an expert software engineer. Break the user request into a concrete multi-file project plan.\n"
            "Respond ONLY with valid JSON of the form:\n"
            '{"project_name":"...", "files":[{"path":"relative/path","description":"..."}], "notes":"..."}\n\n'
            f"User request:\n{prompt}"
        )
        plan_raw = await self.ai.chat(
            [{"role": "user", "content": plan_prompt}],
            role="CODING",
            temperature=0.2,
            max_tokens=2048,
        )
        plan = self._parse_json(plan_raw)
        if not plan or "files" not in plan:
            # Fallback single-file
            plan = {
                "project_name": "project",
                "files": [{"path": "main.py", "description": "Main implementation"}],
                "notes": "",
            }

        project_name = re.sub(r"[^\w\-]", "_", plan.get("project_name", "project"))[:40]
        project_id = await self.db.create_project(user_id, project_name, "")
        root = self.ws.project_dir(user_id, project_id)
        # Update path
        await self.db._db.execute(
            "UPDATE projects SET path=? WHERE project_id=?",
            (str(root), project_id),
        )
        await self.db._db.commit()

        await prog(f"📁 Project `{project_name}` (`{project_id}`)\n" + "\n".join(
            f"• `{f['path']}`" for f in plan["files"][:15]
        ))

        created_files: List[str] = []
        for fmeta in plan["files"]:
            rel = fmeta.get("path", "file.txt")
            await prog(f"🛠️ Creating `{rel}`...")
            gen_prompt = (
                f"Generate the complete content for the file `{rel}`.\n"
                f"Description: {fmeta.get('description', '')}\n"
                f"Overall project goal: {prompt}\n"
                f"Other planned files: {[x['path'] for x in plan['files']]}\n"
                "Return ONLY the raw file content. No markdown fences, no explanation."
            )
            content = await self.ai.chat(
                [{"role": "user", "content": gen_prompt}],
                role="CODING",
                temperature=0.2,
                max_tokens=6000,
            )
            content = self._strip_fences(content)
            self.ws.write_file(user_id, project_id, rel, content)
            created_files.append(rel)
            await prog(f"✅ `{rel}` written ({len(content)} chars)")

        # Test + repair loop
        await prog("🧪 Running tests...")
        for loop in range(self.cfg.max_repair_loops):
            failures = []
            for rel in created_files:
                path = safe_path(root, rel)
                if not path.is_file():
                    continue
                result = await self.tester.test_file(path)
                if not result["ok"]:
                    failures.append((rel, result["message"]))
            if not failures:
                await prog("✅ All tests passed")
                break
            await prog(f"⚠️ Errors found (repair pass {loop + 1}/{self.cfg.max_repair_loops})")
            for rel, err in failures:
                await prog(f"🛠️ Fixing `{rel}`...")
                current = self.ws.read_file(user_id, project_id, rel)
                fix_prompt = (
                    f"The file `{rel}` has the following error:\n```\n{err}\n```\n\n"
                    f"Current content:\n```\n{current[:8000]}\n```\n\n"
                    "Return the COMPLETE corrected file content only. No explanation."
                )
                fixed = await self.ai.chat(
                    [{"role": "user", "content": fix_prompt}],
                    role="CODING",
                    temperature=0.1,
                    max_tokens=6000,
                )
                fixed = self._strip_fences(fixed)
                self.ws.write_file(user_id, project_id, rel, fixed)
                await prog(f"✅ `{rel}` patched")

        # README
        readme_prompt = (
            f"Write a concise README.md for this project.\nGoal: {prompt}\nFiles: {created_files}\n"
            "Include title, description, how to run, and file list."
        )
        readme = await self.ai.chat(
            [{"role": "user", "content": readme_prompt}],
            role="CODING",
            temperature=0.4,
        )
        self.ws.write_file(user_id, project_id, "README.md", self._strip_fences(readme))

        await prog("📦 Packaging ZIP...")
        zip_path = self.ws.zip_project(user_id, project_id)
        summary = (
            f"**Project `{project_name}` complete**\n"
            f"ID: `{project_id}`\n"
            f"Files: {', '.join(f'`{f}`' for f in created_files + ['README.md'])}\n"
            f"Location: `{root}`\n"
        )
        return summary, zip_path

    def _parse_json(self, text: str) -> Optional[dict]:
        text = text.strip()
        # Extract JSON object
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            try:
                return json.loads(m.group(0).replace("'", '"'))
            except Exception:
                return None

    def _strip_fences(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return text


# ---------------------------------------------------------------------------
# SVM AI Router / Agent Core
# ---------------------------------------------------------------------------
class SVMAIAgent:
    def __init__(
        self,
        cfg: Config,
        ai: LocalAIClient,
        search: SearchEngine,
        web: WebTools,
        workspace: Workspace,
        tester: CodeTester,
        github: GitHubAnalyzer,
        seo: SEOAnalyzer,
        coding: CodingAgent,
        db: Database,
    ):
        self.cfg = cfg
        self.ai = ai
        self.search = search
        self.web = web
        self.ws = workspace
        self.tester = tester
        self.github = github
        self.seo = seo
        self.coding = coding
        self.db = db

    SYSTEM_PROMPT = (
        f"You are {BRAND}, an autonomous AI agent created by {AUTHOR}. "
        "You combine advanced reasoning, coding, research, SEO, GitHub analysis, "
        "debugging and multimodal capabilities. Be accurate, helpful and concise. "
        "Never invent sources, URLs or statistics. When you used search results, cite them. "
        "Never reveal private chain-of-thought; present only final useful answers."
    )

    async def route(
        self,
        user_id: int,
        channel_id: int,
        text: str,
        attachments: List[discord.Attachment] = None,
        mode: str = "auto",
        progress_cb: Optional[Callable[[str], Coroutine]] = None,
    ) -> Tuple[str, Optional[discord.File]]:
        attachments = attachments or []
        async def prog(msg: str) -> None:
            if progress_cb:
                with suppress(Exception):
                    await progress_cb(msg)

        session_id = await self.db.get_or_create_session(user_id, channel_id)
        history = await self.db.get_recent_messages(session_id, self.cfg.max_context_messages)

        # Intent
        if mode == "iq200":
            intent = "REASONING"
        elif mode == "deep":
            intent = "DEEP"
        elif mode == "code":
            intent = "CODING"
        elif mode == "research":
            intent = "RESEARCH"
        elif mode == "seo":
            intent = "SEO"
        elif mode == "github":
            intent = "GITHUB"
        elif mode == "debug":
            intent = "DEBUG"
        elif mode == "image":
            intent = "IMAGE"
        elif mode == "vision":
            intent = "VISION"
        elif mode == "url":
            intent = "URL"
        else:
            intent = detect_intent(text)

        # Image attachment → vision
        image_att = next(
            (a for a in attachments if a.content_type and a.content_type.startswith("image/")),
            None,
        )
        if image_att and intent in ("CHAT", "VISION", "DEBUG"):
            intent = "VISION"

        await self.db.add_message(session_id, user_id, "user", text[:10000])

        file_out: Optional[discord.File] = None
        answer = ""

        try:
            if intent == "IMAGE":
                await prog("🎨 Generating image...")
                img_bytes = await self.ai.generate_image(text)
                if img_bytes:
                    file_out = discord.File(io.BytesIO(img_bytes), filename="svmai.png")
                    answer = f"✅ Image generated for: *{text[:200]}*"
                else:
                    answer = (
                        "❌ Image generation failed. "
                        "Ensure LocalAI has an image model or configure IMAGE_PROVIDER / IMAGE_API_KEY."
                    )

            elif intent == "VISION" and image_att:
                await prog("👁️ Analyzing image...")
                data = await image_att.read()
                b64 = base64.b64encode(data).decode()
                mime = image_att.content_type or "image/png"
                prompt = text or "Describe and analyze this image in detail. If it contains code or errors, extract and explain them."
                answer = await self.ai.vision(prompt, b64, mime)

            elif intent == "GITHUB":
                await prog("📦 Analyzing GitHub repository...")
                url_match = re.search(r"https?://github\.com/[^\s]+", text)
                url = url_match.group(0) if url_match else text.strip()
                answer = await self.github.analyze(url)

            elif intent == "SEO":
                await prog("🔍 Running SEO analysis...")
                url_match = re.search(r"https?://[^\s]+", text)
                if url_match:
                    answer = await self.seo.analyze_url(url_match.group(0))
                else:
                    answer = await self.seo.analyze_topic(text)

            elif intent == "CODING":
                summary, zip_path = await self.coding.run(user_id, text, progress_cb=prog)
                answer = summary
                if zip_path and zip_path.exists():
                    file_out = discord.File(str(zip_path), filename=zip_path.name)

            elif intent == "URL":
                await prog("🌐 Fetching URL...")
                url_match = re.search(r"https?://[^\s]+", text)
                if not url_match:
                    answer = "Please provide a valid URL."
                else:
                    page = await self.web.fetch_page(url_match.group(0))
                    if page.get("error"):
                        answer = f"❌ {page['error']}"
                    else:
                        summary_prompt = (
                            "Summarize this webpage for the user. Include title, main points, and key links.\n\n"
                            f"{json.dumps({k: page.get(k) for k in ('url','title','description','headings','text')}, indent=2)[:10000]}"
                        )
                        answer = await self.ai.chat(
                            [{"role": "user", "content": summary_prompt}],
                            role="GENERAL",
                        )

            elif intent in ("RESEARCH", "DEEP", "REASONING") or self._needs_search(text):
                await prog("🔎 Researching...")
                search_ctx = ""
                sources: List[str] = []
                if self.search.available:
                    queries = [text]
                    if intent == "DEEP":
                        # Expand queries via AI
                        expand = await self.ai.chat(
                            [{
                                "role": "user",
                                "content": (
                                    "Generate 3 short distinct web search queries for deep research on:\n"
                                    f"{text}\nRespond with one query per line only."
                                ),
                            }],
                            role="REASONING",
                            temperature=0.3,
                            max_tokens=200,
                        )
                        queries = [q.strip() for q in expand.splitlines() if q.strip()][:4] or [text]
                    all_results = []
                    for q in queries:
                        all_results.extend(await self.search.search(q, num=4))
                    # Deduplicate
                    seen = set()
                    unique = []
                    for r in all_results:
                        u = r.get("url")
                        if u and u not in seen:
                            seen.add(u)
                            unique.append(r)
                    sources = [r["url"] for r in unique[:8]]
                    search_ctx = "\n\n".join(
                        f"[{i+1}] {r['title']}\n{r['url']}\n{r['snippet']}"
                        for i, r in enumerate(unique[:8])
                    )
                    # Optionally open top pages
                    if intent == "DEEP" and unique:
                        await prog("📖 Reading sources...")
                        for r in unique[:3]:
                            page = await self.web.fetch_page(r["url"], max_chars=6000)
                            if not page.get("error"):
                                search_ctx += f"\n\n--- Full extract from {r['url']} ---\n{page.get('text','')[:4000]}"
                else:
                    search_ctx = "(Live search not configured — answering from model knowledge only.)"

                await prog("🧠 Synthesizing...")
                messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
                for h in history[-8:]:
                    messages.append({"role": h["role"], "content": h["content"][:3000]})
                user_content = (
                    f"User question:\n{text}\n\n"
                    f"Search / research context:\n{search_ctx}\n\n"
                    "Provide a thorough, accurate answer. Cite sources by number when used. "
                    "Do not invent facts not present in the context or your knowledge."
                )
                messages.append({"role": "user", "content": user_content})
                role = "REASONING" if intent in ("DEEP", "REASONING") else "GENERAL"
                answer = await self.ai.chat(messages, role=role, temperature=0.4)
                if sources:
                    answer += "\n\n**Sources:**\n" + "\n".join(f"• {s}" for s in sources)

            elif intent == "DEBUG":
                await prog("🐛 Debugging...")
                extra = ""
                if image_att:
                    data = await image_att.read()
                    b64 = base64.b64encode(data).decode()
                    extra = await self.ai.vision(
                        "Extract any error messages, stack traces or code from this image.",
                        b64,
                        image_att.content_type or "image/png",
                    )
                messages = [
                    {"role": "system", "content": self.SYSTEM_PROMPT + " Focus on root-cause analysis and concrete fixes."},
                    {
                        "role": "user",
                        "content": f"Debug this:\n{text}\n\nExtra from image:\n{extra}",
                    },
                ]
                answer = await self.ai.chat(messages, role="CODING", temperature=0.2)

            else:
                # Standard chat
                await prog("💬 Thinking...")
                messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
                for h in history[-self.cfg.max_context_messages:]:
                    messages.append({"role": h["role"], "content": h["content"][:4000]})
                messages.append({"role": "user", "content": text})
                answer = await self.ai.chat(messages, role="GENERAL", temperature=0.7)

        except Exception as e:
            log.exception("Agent error")
            answer = f"❌ Error while processing: {mask_secrets(str(e))}"

        answer = mask_secrets(answer)
        await self.db.add_message(session_id, user_id, "assistant", answer[:20000])
        await self.db.log_usage(user_id, mode or intent)
        return answer, file_out

    def _needs_search(self, text: str) -> bool:
        t = text.lower()
        triggers = (
            "latest", "today", "current", "recent", "2025", "2026", "news",
            "price", "version", "release", "documentation", "search", "research",
            "check", "verify", "find", "what is new", "up to date",
        )
        return any(k in t for k in triggers)


# ---------------------------------------------------------------------------
# Discord Bot
# ---------------------------------------------------------------------------
class SVMAIBot(commands.Bot):
    def __init__(self, cfg: Config):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = False
        super().__init__(command_prefix=cfg.prefix, intents=intents, help_command=None)
        self.cfg = cfg
        self.db = Database(cfg.data_dir / "svm_ai.db")
        self.ai = LocalAIClient(cfg)
        self.search = SearchEngine(cfg)
        self.web = WebTools(cfg)
        self.workspace = Workspace(cfg.workspace_dir)
        self.tester = CodeTester(cfg)
        self.github = GitHubAnalyzer(cfg, self.ai)
        self.seo = SEOAnalyzer(self.web, self.ai, self.search)
        self.coding = CodingAgent(cfg, self.ai, self.workspace, self.tester, self.db)
        self.agent = SVMAIAgent(
            cfg, self.ai, self.search, self.web, self.workspace,
            self.tester, self.github, self.seo, self.coding, self.db,
        )
        self.limiter = RateLimiter(cfg.user_cooldown)
        self.start_time = time.time()
        self._ready = False

    async def setup_hook(self) -> None:
        await self.db.connect()
        await self.ai.start()
        # Register slash commands
        self.tree.add_command(self.ask_slash)
        self.tree.add_command(self.iq200_slash)
        self.tree.add_command(self.deep_slash)
        self.tree.add_command(self.research_slash)
        self.tree.add_command(self.seo_slash)
        self.tree.add_command(self.code_slash)
        self.tree.add_command(self.github_slash)
        self.tree.add_command(self.debug_slash)
        self.tree.add_command(self.image_slash)
        self.tree.add_command(self.vision_slash)
        self.tree.add_command(self.url_slash)
        self.tree.add_command(self.status_slash)
        self.tree.add_command(self.models_slash)
        self.tree.add_command(self.project_slash)
        self.tree.add_command(self.help_slash)
        try:
            synced = await self.tree.sync()
            log.info("Synced %d slash commands", len(synced))
        except Exception as e:
            log.warning("Slash sync failed: %s", e)

    async def on_ready(self) -> None:
        if self._ready:
            return
        self._ready = True
        log.info("%s online as %s (id=%s)", BRAND, self.user, self.user.id if self.user else "?")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"{self.cfg.prefix}help | /ask",
            )
        )

    async def close(self) -> None:
        await self.ai.close()
        await self.db.close()
        await super().close()

    # ---- helpers ----
    async def _check_rate(self, user: discord.User | discord.Member) -> Optional[str]:
        if not self.cfg.rate_limit_enabled:
            return None
        ok, rem = self.limiter.check(
            user.id,
            is_admin=self.cfg.is_admin(user.id),
            bypass=self.cfg.admin_bypass_rate_limit,
        )
        if not ok:
            return f"⏳ Slow down — try again in {rem:.1f}s"
        return None

    async def _send_answer(
        self,
        target: Union[discord.Interaction, commands.Context],
        text: str,
        file: Optional[discord.File] = None,
        ephemeral: bool = False,
    ) -> None:
        chunks = smart_chunk(text, self.cfg.max_message_length)
        is_interaction = isinstance(target, discord.Interaction)

        async def send_one(content: str, first: bool = False, f: Optional[discord.File] = None):
            if is_interaction:
                if first:
                    if target.response.is_done():
                        await target.followup.send(content, file=f, ephemeral=ephemeral)
                    else:
                        await target.response.send_message(content, file=f, ephemeral=ephemeral)
                else:
                    await target.followup.send(content, ephemeral=ephemeral)
            else:
                await target.send(content, file=f if first else None)

        for i, chunk in enumerate(chunks):
            await send_one(chunk, first=(i == 0), f=file if i == 0 else None)

    async def _run_agent(
        self,
        ctx_or_inter: Union[discord.Interaction, commands.Context],
        prompt: str,
        mode: str = "auto",
        attachments: List[discord.Attachment] = None,
    ) -> None:
        user = ctx_or_inter.user if isinstance(ctx_or_inter, discord.Interaction) else ctx_or_inter.author
        channel = ctx_or_inter.channel
        rate_msg = await self._check_rate(user)
        if rate_msg:
            if isinstance(ctx_or_inter, discord.Interaction):
                await ctx_or_inter.response.send_message(rate_msg, ephemeral=True)
            else:
                await ctx_or_inter.send(rate_msg)
            return

        await self.db.ensure_user(user.id, str(user))

        # Progress message
        is_inter = isinstance(ctx_or_inter, discord.Interaction)
        if is_inter:
            await ctx_or_inter.response.defer(thinking=True)
            progress_msg = None
        else:
            progress_msg = await ctx_or_inter.send("⏳ Processing...")

        last_edit = 0.0

        async def progress_cb(msg: str) -> None:
            nonlocal last_edit
            now = time.monotonic()
            if now - last_edit < 1.2:
                return
            last_edit = now
            try:
                if progress_msg:
                    await progress_msg.edit(content=msg[:1900])
            except Exception:
                pass

        try:
            answer, file_out = await self.agent.route(
                user.id,
                channel.id if channel else 0,
                prompt,
                attachments=attachments or [],
                mode=mode,
                progress_cb=progress_cb,
            )
            if progress_msg:
                with suppress(Exception):
                    await progress_msg.delete()
            await self._send_answer(ctx_or_inter, answer, file=file_out)
        except Exception as e:
            log.exception("Command error")
            err = f"❌ Unexpected error: {mask_secrets(str(e))}"
            if progress_msg:
                with suppress(Exception):
                    await progress_msg.edit(content=err)
            else:
                await self._send_answer(ctx_or_inter, err)

    # ---- Slash commands ----
    @app_commands.command(name="ask", description="Universal AI agent — auto-routes tools")
    @app_commands.describe(prompt="Your question or task")
    async def ask_slash(self, interaction: discord.Interaction, prompt: str) -> None:
        await self._run_agent(interaction, prompt, mode="auto")

    @app_commands.command(name="iq200", description="Highest reasoning mode")
    @app_commands.describe(prompt="Complex question requiring deep reasoning")
    async def iq200_slash(self, interaction: discord.Interaction, prompt: str) -> None:
        await self._run_agent(interaction, prompt, mode="iq200")

    @app_commands.command(name="deep", description="Deep multi-source research")
    @app_commands.describe(prompt="Topic to research thoroughly")
    async def deep_slash(self, interaction: discord.Interaction, prompt: str) -> None:
        await self._run_agent(interaction, prompt, mode="deep")

    @app_commands.command(name="research", description="Web research + synthesis")
    @app_commands.describe(prompt="Research query")
    async def research_slash(self, interaction: discord.Interaction, prompt: str) -> None:
        await self._run_agent(interaction, prompt, mode="research")

    @app_commands.command(name="seo", description="SEO analysis for URL or topic")
    @app_commands.describe(target="URL or keyword topic")
    async def seo_slash(self, interaction: discord.Interaction, target: str) -> None:
        await self._run_agent(interaction, target, mode="seo")

    @app_commands.command(name="code", description="Multi-file coding agent")
    @app_commands.describe(prompt="What to build")
    async def code_slash(self, interaction: discord.Interaction, prompt: str) -> None:
        await self._run_agent(interaction, prompt, mode="code")

    @app_commands.command(name="github", description="Analyze a public GitHub repository")
    @app_commands.describe(url="https://github.com/owner/repo")
    async def github_slash(self, interaction: discord.Interaction, url: str) -> None:
        await self._run_agent(interaction, url, mode="github")

    @app_commands.command(name="debug", description="Debug errors, traces, logs")
    @app_commands.describe(error="Error message, traceback or description")
    async def debug_slash(self, interaction: discord.Interaction, error: str) -> None:
        await self._run_agent(interaction, error, mode="debug")

    @app_commands.command(name="image", description="Generate an image")
    @app_commands.describe(prompt="Image description")
    async def image_slash(self, interaction: discord.Interaction, prompt: str) -> None:
        await self._run_agent(interaction, prompt, mode="image")

    @app_commands.command(name="vision", description="Analyze an attached image")
    @app_commands.describe(prompt="What to look for (optional)")
    async def vision_slash(self, interaction: discord.Interaction, prompt: str = "Describe this image in detail") -> None:
        atts = []
        # Interaction may not have message attachments easily; user should attach in follow-up or use prefix
        await self._run_agent(interaction, prompt, mode="vision", attachments=atts)

    @app_commands.command(name="url", description="Fetch and summarize a URL")
    @app_commands.describe(url="http(s) URL")
    async def url_slash(self, interaction: discord.Interaction, url: str) -> None:
        await self._run_agent(interaction, url, mode="url")

    @app_commands.command(name="status", description="System health status")
    async def status_slash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        health = await self.ai.health()
        uptime = int(time.time() - self.start_time)
        hours, rem = divmod(uptime, 3600)
        mins, secs = divmod(rem, 60)
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.3)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            sysinfo = f"CPU {cpu}% · RAM {mem.percent}% · Disk {disk.percent}%"
        except Exception:
            sysinfo = "N/A"
        lines = [
            f"**{BRAND}** v{VERSION} · Made by {AUTHOR}",
            f"{'🟢' if self.is_ready() else '🔴'} Discord",
            f"{'🟢' if health.get('healthy') else '🔴'} LocalAI ({health.get('url')})",
            f"{'🟢' if health.get('models') else '🟡'} Models: {len(health.get('models') or [])}",
            f"{'🟢' if self.search.available else '🟡'} Search ({self.cfg.search_provider or 'none'})",
            f"{'🟢' if (self.cfg.image_api_key or self.ai.select_model('IMAGE')) else '🟡'} Image",
            f"🟢 Database · 🟢 Workspace",
            f"⏱ Uptime {hours}h {mins}m {secs}s",
            f"🖥 {sysinfo}",
        ]
        if health.get("selected"):
            sel = health["selected"]
            lines.append(
                f"Models → general=`{sel.get('general')}` coding=`{sel.get('coding')}` "
                f"reasoning=`{sel.get('reasoning')}`"
            )
        await interaction.followup.send("\n".join(lines))

    @app_commands.command(name="models", description="List LocalAI models")
    async def models_slash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        health = await self.ai.health()
        models = health.get("models") or []
        sel = health.get("selected") or {}
        text = (
            f"**LocalAI** `{health.get('url')}`\n"
            f"Healthy: {'✅' if health.get('healthy') else '❌'}\n\n"
            f"**Selected**\n"
            f"• General: `{sel.get('general')}`\n"
            f"• Coding: `{sel.get('coding')}`\n"
            f"• Reasoning: `{sel.get('reasoning')}`\n"
            f"• Vision: `{sel.get('vision')}`\n"
            f"• Image: `{sel.get('image')}`\n\n"
            f"**Available ({len(models)})**\n"
            + ("\n".join(f"• `{m}`" for m in models[:40]) or "_none detected_")
        )
        await interaction.followup.send(text[:1900])

    @app_commands.command(name="project", description="List or manage your projects")
    @app_commands.describe(action="list | zip | delete", project_id="Project ID for zip/delete")
    async def project_slash(
        self, interaction: discord.Interaction, action: str = "list", project_id: str = ""
    ) -> None:
        await interaction.response.defer(thinking=True)
        user = interaction.user
        action = action.lower().strip()
        if action == "list":
            projects = await self.db.list_projects(user.id)
            if not projects:
                await interaction.followup.send("No projects yet. Use `/code` to create one.")
                return
            lines = [f"**Your projects** ({len(projects)})"]
            for p in projects[:20]:
                lines.append(f"• `{p['project_id']}` — **{p['name']}** ({p['created_at'][:10]})")
            await interaction.followup.send("\n".join(lines))
        elif action == "zip" and project_id:
            proj = await self.db.get_project(project_id, user.id)
            if not proj:
                await interaction.followup.send("Project not found.")
                return
            try:
                zp = self.workspace.zip_project(user.id, project_id)
                await interaction.followup.send(
                    f"📦 Project `{project_id}`",
                    file=discord.File(str(zp), filename=zp.name),
                )
            except Exception as e:
                await interaction.followup.send(f"❌ {e}")
        elif action == "delete" and project_id:
            await self.db.delete_project(project_id, user.id)
            try:
                pdir = self.workspace.project_dir(user.id, project_id)
                if pdir.exists():
                    shutil.rmtree(pdir, ignore_errors=True)
            except Exception:
                pass
            await interaction.followup.send(f"🗑️ Project `{project_id}` deleted.")
        else:
            await interaction.followup.send("Usage: `/project action:list|zip|delete project_id:...`")

    @app_commands.command(name="help", description="SVM AI help")
    async def help_slash(self, interaction: discord.Interaction) -> None:
        text = self._help_text()
        await interaction.response.send_message(text, ephemeral=True)

    def _help_text(self) -> str:
        p = self.cfg.prefix
        return (
            f"**{BRAND}** v{VERSION} — Made by {AUTHOR}\n"
            f"Autonomous Discord AI Agent powered by **LocalAI**\n\n"
            f"**Universal**\n"
            f"`/ask` `{p}ask` — auto-routes tools\n"
            f"`/iq200` `{p}iq200` — max reasoning\n"
            f"`/deep` `{p}deep` — deep research\n"
            f"`/research` `{p}research` — web research\n\n"
            f"**Specialized**\n"
            f"`/code` `{p}code` — multi-file coding agent\n"
            f"`/github` `{p}github` — repo analysis\n"
            f"`/seo` `{p}seo` — SEO audit / keywords\n"
            f"`/debug` `{p}debug` — error analysis\n"
            f"`/url` `{p}url` — page summary\n"
            f"`/image` `{p}image` — image generation\n"
            f"`/vision` `{p}vision` — image understanding\n"
            f"`/project` — list / zip / delete projects\n\n"
            f"**System**\n"
            f"`/status` `{p}status` · `/models` `{p}models` · `/help`\n"
        )


# ---------------------------------------------------------------------------
# Prefix command registration (outside class for clarity)
# ---------------------------------------------------------------------------
def register_prefix_commands(bot: SVMAIBot) -> None:
    @bot.command(name="ask", aliases=["ai"])
    async def ask_cmd(ctx: commands.Context, *, prompt: str = "") -> None:
        if not prompt:
            await ctx.send("Usage: `!ask <message>`")
            return
        atts = list(ctx.message.attachments)
        await bot._run_agent(ctx, prompt, mode="auto", attachments=atts)

    @bot.command(name="iq200")
    async def iq200_cmd(ctx: commands.Context, *, prompt: str = "") -> None:
        if not prompt:
            await ctx.send("Usage: `!iq200 <prompt>`")
            return
        await bot._run_agent(ctx, prompt, mode="iq200", attachments=list(ctx.message.attachments))

    @bot.command(name="deep")
    async def deep_cmd(ctx: commands.Context, *, prompt: str = "") -> None:
        if not prompt:
            await ctx.send("Usage: `!deep <topic>`")
            return
        await bot._run_agent(ctx, prompt, mode="deep")

    @bot.command(name="research")
    async def research_cmd(ctx: commands.Context, *, prompt: str = "") -> None:
        if not prompt:
            await ctx.send("Usage: `!research <query>`")
            return
        await bot._run_agent(ctx, prompt, mode="research")

    @bot.command(name="seo")
    async def seo_cmd(ctx: commands.Context, *, target: str = "") -> None:
        if not target:
            await ctx.send("Usage: `!seo <url|topic>`")
            return
        await bot._run_agent(ctx, target, mode="seo")

    @bot.command(name="code")
    async def code_cmd(ctx: commands.Context, *, prompt: str = "") -> None:
        if not prompt:
            await ctx.send("Usage: `!code <what to build>`")
            return
        await bot._run_agent(ctx, prompt, mode="code")

    @bot.command(name="github")
    async def github_cmd(ctx: commands.Context, *, url: str = "") -> None:
        if not url:
            await ctx.send("Usage: `!github <repo-url>`")
            return
        await bot._run_agent(ctx, url, mode="github")

    @bot.command(name="debug")
    async def debug_cmd(ctx: commands.Context, *, error: str = "") -> None:
        if not error and not ctx.message.attachments:
            await ctx.send("Usage: `!debug <error/traceback>` (attachments supported)")
            return
        await bot._run_agent(ctx, error or "Analyze attached image/error", mode="debug",
                             attachments=list(ctx.message.attachments))

    @bot.command(name="image")
    async def image_cmd(ctx: commands.Context, *, prompt: str = "") -> None:
        if not prompt:
            await ctx.send("Usage: `!image <description>`")
            return
        await bot._run_agent(ctx, prompt, mode="image")

    @bot.command(name="vision")
    async def vision_cmd(ctx: commands.Context, *, prompt: str = "Describe this image") -> None:
        if not ctx.message.attachments:
            await ctx.send("Attach an image and use `!vision [optional prompt]`")
            return
        await bot._run_agent(ctx, prompt, mode="vision", attachments=list(ctx.message.attachments))

    @bot.command(name="url")
    async def url_cmd(ctx: commands.Context, *, url: str = "") -> None:
        if not url:
            await ctx.send("Usage: `!url <https://...>`")
            return
        await bot._run_agent(ctx, url, mode="url")

    @bot.command(name="status")
    async def status_cmd(ctx: commands.Context) -> None:
        # Reuse slash logic via a fake interaction-like path
        health = await bot.ai.health()
        uptime = int(time.time() - bot.start_time)
        h, rem = divmod(uptime, 3600)
        m, s = divmod(rem, 60)
        text = (
            f"**{BRAND}** v{VERSION}\n"
            f"{'🟢' if bot.is_ready() else '🔴'} Discord\n"
            f"{'🟢' if health.get('healthy') else '🔴'} LocalAI\n"
            f"Models: {len(health.get('models') or [])}\n"
            f"Search: {'🟢' if bot.search.available else '🟡'}\n"
            f"Uptime: {h}h {m}m {s}s"
        )
        await ctx.send(text)

    @bot.command(name="models")
    async def models_cmd(ctx: commands.Context) -> None:
        health = await bot.ai.health()
        models = health.get("models") or []
        text = f"**Models ({len(models)})**\n" + "\n".join(f"• `{m}`" for m in models[:30])
        await ctx.send(text[:1900] or "No models detected.")

    @bot.command(name="help")
    async def help_cmd(ctx: commands.Context) -> None:
        await ctx.send(bot._help_text())

    @bot.command(name="project")
    async def project_cmd(ctx: commands.Context, action: str = "list", project_id: str = "") -> None:
        user = ctx.author
        action = action.lower()
        if action == "list":
            projects = await bot.db.list_projects(user.id)
            if not projects:
                await ctx.send("No projects. Use `!code` to create one.")
                return
            lines = [f"**Projects** ({len(projects)})"]
            for p in projects[:15]:
                lines.append(f"`{p['project_id']}` — {p['name']}")
            await ctx.send("\n".join(lines))
        elif action == "zip" and project_id:
            proj = await bot.db.get_project(project_id, user.id)
            if not proj:
                await ctx.send("Not found.")
                return
            zp = bot.workspace.zip_project(user.id, project_id)
            await ctx.send(file=discord.File(str(zp), filename=zp.name))
        elif action == "delete" and project_id:
            await bot.db.delete_project(project_id, user.id)
            await ctx.send(f"Deleted `{project_id}`")
        else:
            await ctx.send("Usage: `!project list|zip|delete [id]`")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    cfg = Config.load()
    global log
    log = setup_logging(str(cfg.log_dir), cfg.log_level)

    if not cfg.discord_token:
        print("=" * 50)
        print("  SVM AI — Missing DISCORD_TOKEN")
        print("  Set it in .env or run: sudo bash install.sh")
        print("=" * 50)
        sys.exit(1)

    bot = SVMAIBot(cfg)
    register_prefix_commands(bot)

    def _shutdown(*_):
        log.info("Shutting down...")
        asyncio.get_event_loop().create_task(bot.close())

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        bot.run(cfg.discord_token, log_handler=None)
    except discord.LoginFailure:
        print("❌ Invalid DISCORD_TOKEN")
        sys.exit(1)
    except Exception as e:
        log.exception("Fatal: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
