"""
GitHub API utilities: rate-limit detection, retry with backoff,
terminal state detection, and token sanitization.

Adapted from link-assistant/hive-mind:
- github-rate-limit.lib.mjs
- github-terminal-state.lib.mjs
- token-sanitization.lib.mjs

Wait policy: wait = (resetTimestamp - now) + buffer_seconds + random(jitter_seconds)
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# === Configuration ===

DEFAULT_RATE_LIMIT_BUFFER_SECONDS = 600  # 10 min buffer after reset
DEFAULT_RATE_LIMIT_JITTER_SECONDS = 300   # 0-5 min random jitter
DEFAULT_TRANSIENT_RETRY_COUNT = 3
DEFAULT_TRANSIENT_RETRY_DELAY = 5  # seconds

RATE_LIMIT_PATTERNS = [
    "api rate limit exceeded",
    "rate limit exceeded",
    "you have exceeded a secondary rate limit",
    "secondary rate limit",
    "abuse detection",
    "was submitted too quickly",
]

TERMINAL_ENTITY_PATTERNS = [
    r"\bHTTP\s+404\b",
    r"\bHTTP\s+410\b",
    r"\b404\s+Not Found\b",
    r"\b410\s+Gone\b",
    r'\bstatus["\']?\s*:\s*["\']?404\b',
    r'\bstatus["\']?\s*:\s*["\']?410\b',
    r"Could not resolve to a Repository",
    r"Could not resolve to a PullRequest",
    r"Could not resolve to an Issue",
    r"Could not resolve to a Branch",
    r"repository not found",
    r"\bgh:\s*Not Found\b",
]


def _collect_error_text(error: object) -> str:
    """Extract all text from an error for pattern matching."""
    if not error:
        return ""
    if isinstance(error, str):
        return error
    parts = []
    if isinstance(error, Exception):
        parts.append(str(error))
    if hasattr(error, "stderr"):
        parts.append(str(error.stderr))
    if hasattr(error, "stdout"):
        parts.append(str(error.stdout))
    return "\n".join(parts)


# === Rate Limit Detection ===

def is_rate_limit_error(error: object) -> bool:
    """Check if error represents a GitHub rate-limit response.

    Recognises both primary (5000/hr) and secondary (abuse-detection) forms.
    """
    text = _collect_error_text(error).lower()
    if not text:
        return False
    return any(pattern in text for pattern in RATE_LIMIT_PATTERNS)


def parse_rate_limit_reset(error: object) -> Optional[datetime]:
    """Extract rate-limit reset time from error text.

    Priority:
    1. X-RateLimit-Reset header (Unix epoch seconds)
    2. Retry-After header (seconds from now)
    3. None — caller should poll gh api rate_limit
    """
    text = _collect_error_text(error)
    if not text:
        return None

    # X-RateLimit-Reset: Unix epoch seconds
    reset_match = re.search(r"x-ratelimit-reset:\s*(\d+)", text, re.IGNORECASE)
    if reset_match:
        epoch = int(reset_match.group(1))
        if epoch > 0:
            return datetime.fromtimestamp(epoch, tz=timezone.utc)

    # Retry-After: seconds from now
    retry_match = re.search(r"retry-after:\s*(\d+)", text, re.IGNORECASE)
    if retry_match:
        seconds = int(retry_match.group(1))
        if seconds >= 0:
            return datetime.now(timezone.utc).replace(microsecond=0)

    return None


async def fetch_next_rate_limit_reset() -> Optional[datetime]:
    """Query gh api rate_limit for the most restrictive reset time."""
    try:
        result = subprocess.run(
            ["gh", "api", "rate_limit"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        resources = data.get("resources", {})
        candidates = []
        for key in ("core", "graphql", "search"):
            r = resources.get(key, {})
            reset_epoch = r.get("reset")
            if reset_epoch:
                candidates.append(datetime.fromtimestamp(reset_epoch, tz=timezone.utc))
        if candidates:
            return min(candidates)
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return None


def compute_rate_limit_wait_seconds(reset_time: datetime) -> float:
    """Compute how long to wait: (reset - now) + buffer + jitter."""
    now = datetime.now(timezone.utc)
    if reset_time.tzinfo is None:
        reset_time = reset_time.replace(tzinfo=timezone.utc)
    wait = (reset_time - now).total_seconds()
    wait += DEFAULT_RATE_LIMIT_BUFFER_SECONDS
    wait += random.uniform(0, DEFAULT_RATE_LIMIT_JITTER_SECONDS)
    return max(wait, 0)


# === Terminal State Detection ===

def is_terminal_entity_error(error: object) -> bool:
    """Detect terminal GitHub entity states (404, 410, deleted/inaccessible).

    These are NOT transient — retrying indefinitely wastes time and tokens.
    """
    text = _collect_error_text(error)
    if not text:
        return False
    return any(re.search(p, text) for p in TERMINAL_ENTITY_PATTERNS)


def get_terminal_entity_error_message(error: object, fallback: str = "GitHub entity is no longer accessible") -> str:
    """Get a human-readable message for a terminal entity error."""
    text = _collect_error_text(error)
    if not text:
        return fallback
    return " ".join(line.strip() for line in text.split("\n") if line.strip()) or fallback


# === Token Sanitization ===

def sanitize_for_logs(text: str) -> str:
    """Remove GitHub tokens and secrets from log output."""
    if not text:
        return text
    # Replace common token patterns
    text = re.sub(r"(gh[oprs]_[A-Za-z0-9_]{20,})", "***REDACTED***", text)
    text = re.sub(r"(ghp_[A-Za-z0-9]{36})", "***REDACTED***", text)
    text = re.sub(
        r"(token\s*[:=]\s*)([^\s\"']{8,})", r"\1***REDACTED***", text,
        flags=re.IGNORECASE,
    )
    return text


# === Retry Wrapper ===

@dataclass
class RetryConfig:
    """Configuration for retry with rate-limit awareness."""
    max_transient_retries: int = DEFAULT_TRANSIENT_RETRY_COUNT
    transient_retry_delay: float = DEFAULT_TRANSIENT_RETRY_DELAY
    rate_limit_buffer: int = DEFAULT_RATE_LIMIT_BUFFER_SECONDS
    rate_limit_jitter: int = DEFAULT_RATE_LIMIT_JITTER_SECONDS


def retry_with_rate_limit(func, config: Optional[RetryConfig] = None):
    """Call func() with automatic retry for transient errors and rate-limit backoff.

    Usage:
        result = retry_with_rate_limit(lambda: gh.create_pr(title="...", ...))
    """
    if config is None:
        config = RetryConfig()
    last_error = None
    for attempt in range(config.max_transient_retries + 1):
        try:
            return func()
        except RuntimeError as e:
            error_text = str(e)
            last_error = e

            # Terminal state — don't retry
            if is_terminal_entity_error(error_text):
                logger.error("Terminal GitHub entity error, not retrying: %s",
                             get_terminal_entity_error_message(error_text))
                raise

            # Rate limit — compute precise wait
            if is_rate_limit_error(error_text):
                reset_time = parse_rate_limit_reset(error_text)
                if reset_time is None:
                    # Fallback: poll rate_limit endpoint
                    # (sync version for simplicity)
                    logger.warning("Rate limit detected, polling reset time...")
                    try:
                        import asyncio
                        reset_time = asyncio.get_event_loop().run_until_complete(
                            fetch_next_rate_limit_reset()
                        )
                    except Exception:
                        pass
                if reset_time:
                    wait = compute_rate_limit_wait_seconds(reset_time)
                    logger.warning(
                        "GitHub rate limit hit. Waiting %.0f seconds (reset at %s)",
                        wait, reset_time.isoformat(),
                    )
                    time.sleep(wait)
                    continue
                else:
                    # Could not determine reset time, use exponential backoff
                    wait = config.transient_retry_delay * (2 ** attempt)
                    logger.warning("GitHub rate limit hit, waiting %.0f s (unknown reset)", wait)
                    time.sleep(wait)
                    continue

            # Transient error (network, etc.) — standard backoff
            if attempt < config.max_transient_retries:
                wait = config.transient_retry_delay * (2 ** attempt)
                logger.warning("Transient error (attempt %d/%d), retrying in %.0f s: %s",
                               attempt + 1, config.max_transient_retries, wait, e)
                time.sleep(wait)
                continue

            raise

    raise last_error or RuntimeError("Max retries exceeded in retry_with_rate_limit")
