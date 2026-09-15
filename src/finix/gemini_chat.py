"""Grounded Gemini responses for the FiniX investigation copilot.

Only compact, dashboard-safe evidence is sent to Gemini. Raw KYC identity
fields, full complaint text, PAN, Aadhaar, and settlement-account data are
never included in prompts.
"""
from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

from .core import PROJECT_ROOT
from .investigation import InvestigationResult, investigate


ENV_FILE = PROJECT_ROOT / "env" / ".env"
DEFAULT_MODEL = "gemini-2.5-flash"
SYSTEM_INSTRUCTION = """You are FiniX Copilot, a financial-risk investigation assistant.
Use only the evidence supplied in the user prompt. Do not infer or invent facts,
IDs, risk labels, values, relationships, timestamps, or data-quality results.
Never say an entity is fraudulent, criminal, guilty, or definitely suspicious.
Use wording such as investigation candidate, observed signal, and requires review.
Explain limitations where evidence is missing. Do not request, expose, or infer
PAN, Aadhaar, full name, settlement account, or other sensitive data.
Give concise, business-ready answers with observed signals."""


@dataclass(frozen=True)
class GeminiReply:
    """A chat response paired with its deterministic evidence result."""

    text: str
    evidence: InvestigationResult
    provider: str


def load_gemini_config() -> tuple[str | None, str]:
    """Load configuration from local env file, environment variables, or Streamlit secrets."""
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            name, value = line.split("=", maxsplit=1)
            clean_name = name.strip()
            clean_value = value.strip().strip("\"'").strip()
            os.environ[clean_name] = clean_value
    key = os.getenv("GEMINI_API_KEY", "").strip().strip("\"'").strip() or None
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip().strip("\"'").strip() or DEFAULT_MODEL
    if not key:
        try:
            import streamlit as st
            if "GEMINI_API_KEY" in st.secrets:
                key = str(st.secrets["GEMINI_API_KEY"]).strip().strip("\"'").strip() or None
            if "GEMINI_MODEL" in st.secrets:
                model = str(st.secrets["GEMINI_MODEL"]).strip().strip("\"'").strip() or model
        except Exception:
            pass
    return key, model


def _valid_gemini_key(key: str | None) -> bool:
    """Return True only for a key that passes a basic format sanity check."""
    if not key:
        return False
    clean = key.strip().strip("\"'").strip()
    if not clean or len(clean) < 10:
        return False
    if any(placeholder in clean.upper() for placeholder in ("PASTE_YOUR", "YOUR_KEY", "PLACEHOLDER")):
        return False
    return True


def gemini_available() -> bool:
    """Return whether a valid, non-placeholder Gemini key has been configured."""
    key, _ = load_gemini_config()
    return _valid_gemini_key(key)


def ask_gemini(query: str, data: Mapping[str, pd.DataFrame]) -> GeminiReply:
    """Ground Gemini in deterministic FiniX evidence with a safe fallback."""
    evidence = investigate(query, data)
    key, model = load_gemini_config()
    if not _valid_gemini_key(key):
        reason = "Gemini is not configured yet." if not key else "Gemini API key is not configured. Please set GEMINI_API_KEY in env/.env."
        return GeminiReply(_fallback_text(evidence, reason), evidence, "deterministic fallback")

    try:
        payload = json.dumps(
            {
                "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                "contents": [{"role": "user", "parts": [{"text": _prompt(query, evidence)}]}],
                "generationConfig": {"temperature": 0.15, "maxOutputTokens": 600},
            }
        ).encode("utf-8")
        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=8) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = "".join(part.get("text", "") for part in body.get("candidates", [{}])[0].get("content", {}).get("parts", [])).strip()
        if not text:
            return GeminiReply(_fallback_text(evidence, "Gemini returned no text."), evidence, "deterministic fallback")
        return GeminiReply(text, evidence, f"Gemini ({model})")
    except (HTTPError, URLError, TimeoutError, ValueError, IndexError, OSError, socket.error) as error:
        return GeminiReply(_fallback_text(evidence, f"Gemini request unavailable: {type(error).__name__}."), evidence, "deterministic fallback")


def _prompt(query: str, evidence: InvestigationResult) -> str:
    """Create a compact evidence-only prompt with a maximum 25-row sample."""
    frame = evidence.data.head(25).copy()
    rows = []
    if not frame.empty:
        frame = frame.where(pd.notna(frame), None)
        rows = json.loads(frame.to_json(orient="records", date_format="iso"))
    payload = {
        "user_question": query,
        "deterministic_result_title": evidence.title,
        "deterministic_explanation": evidence.explanation,
        "evidence_row_count": len(evidence.data),
        "evidence_sample_max_25_rows": rows,
    }
    return "Answer the user question using only this FiniX evidence JSON:\n" + json.dumps(payload, ensure_ascii=False)


def _fallback_text(evidence: InvestigationResult, reason: str) -> str:
    """Return data-backed output when the external model cannot be used."""
    return f"**{evidence.title}**\n\n{evidence.explanation}\n\n_{reason} Showing the deterministic, data-backed FiniX result instead._"
