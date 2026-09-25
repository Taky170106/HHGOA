"""Llm layer (Phase 4) — Google AI Studio / Gemma, with honest degradation.

Contract:
  * The key lives only in ``.env`` (gitignored). It is never printed, never
    written into a run artifact, never sent anywhere but the provider.
  * If no key/provider is reachable, the client reports
    ``status = "no_llm_available"`` with ``tokens = 0`` — it never fabricates
    text, token counts, or a model name.
  * Every real call records provider, model, latency and the token counts the
    API itself returned.

Used by the LangGraph ``summary`` node; until a call succeeds, that node falls
back to the deterministic narrative built from graph evidence.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from typing import Any, Dict, Optional

if not getattr(sys.stdout, "_hhg_wrapped", False):
    _w = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _w._hhg_wrapped = True
    sys.stdout = _w

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Wall-clock ceiling for ONE provider call. Measured spread on this model is
# 16 s (34 input tokens) to 261 s (234 tokens) for the same request, so a bound
# is required to keep a run predictable.
_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "45"))

_ENV_LOADED: Optional[Dict[str, str]] = None


def _load_env() -> Dict[str, str]:
    """Read .env (and the process environment) without ever echoing values."""
    global _ENV_LOADED
    if _ENV_LOADED is not None:
        return _ENV_LOADED
    vals: Dict[str, str] = {}
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    vals[k.strip()] = v.strip()
        except OSError:
            pass
    for k in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL"):
        if os.getenv(k):
            vals[k] = os.getenv(k) or ""
    _ENV_LOADED = vals
    return vals


def status() -> Dict[str, Any]:
    """What the LLM layer can do right now — no secrets, no guesses."""
    env = _load_env()
    key = env.get("LLM_API_KEY") or ""
    provider = (env.get("LLM_PROVIDER") or "").strip().lower() or "google"
    model = (env.get("LLM_MODEL") or "").strip()
    configured = bool(key) and key not in ("placeholder-rotated-away", "replace-at-runtime")
    if not configured:
        return {"available": False, "provider": provider, "model": model,
                "reason": "no LLM_API_KEY in .env", "tokens": 0}
    if provider == "google":
        try:
            from google import genai  # noqa: F401
            sdk = "google-genai"
        except Exception as exc:
            return {"available": False, "provider": provider, "model": model,
                    "reason": "google-genai SDK unavailable: %s" % exc, "tokens": 0}
    else:
        sdk = "openai-compatible-http"
    return {"available": True, "provider": provider, "model": model,
            "sdk": sdk, "base_url": env.get("LLM_BASE_URL", ""),
            "reason": "key present", "tokens": 0}


def _generate_google(model: str, prompt: str, system: Optional[str],
                     temperature: float, max_output_tokens: int) -> Dict[str, Any]:
    from google import genai
    from google.genai import types

    env = _load_env()
    # The key is passed to the SDK, never logged and never returned.
    # A hard timeout bounds this call: measured Gemma latency ranges from 16 s
    # to 261 s on identical prompts, and an unbounded call would stall a whole
    # investigation run.
    client = None
    for opts in (types.HttpOptions(timeout=int(_TIMEOUT_S * 1000)), None):
        try:
            client = (genai.Client(api_key=env["LLM_API_KEY"], http_options=opts)
                      if opts is not None else genai.Client(api_key=env["LLM_API_KEY"]))
            break
        except Exception:
            client = None
    if client is None:
        client = genai.Client(api_key=env["LLM_API_KEY"])

    contents = prompt if not system else "%s\n\n%s" % (system, prompt)
    cfg = types.GenerateContentConfig(temperature=temperature,
                                      max_output_tokens=max_output_tokens)
    resp = client.models.generate_content(model=model, contents=contents, config=cfg)
    um = getattr(resp, "usage_metadata", None) or {}
    return {
        "text": getattr(resp, "text", None) or "",
        "tokens_in": int(getattr(um, "prompt_token_count", 0) or 0),
        "tokens_out": int(getattr(um, "candidates_token_count", 0) or 0),
        "tokens_total": int(getattr(um, "total_token_count", 0) or 0),
    }


def _generate_openai(model: str, prompt: str, system: Optional[str],
                     temperature: float, max_output_tokens: int) -> Dict[str, Any]:
    import urllib.request

    env = _load_env()
    base = (env.get("LLM_BASE_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("LLM_BASE_URL missing for openai-compatible provider")
    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
    body = json.dumps({"model": model, "messages": messages,
                       "temperature": temperature,
                       "max_tokens": max_output_tokens}).encode("utf-8")
    req = urllib.request.Request(
        base + "/chat/completions", data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + env["LLM_API_KEY"]})
    with urllib.request.urlopen(req, timeout=120) as r:
        payload = json.loads(r.read().decode("utf-8", "replace"))
    usage = payload.get("usage") or {}
    text = ""
    try:
        text = payload["choices"][0]["message"]["content"] or ""
    except Exception:
        pass
    return {"text": text,
            "tokens_in": int(usage.get("prompt_tokens", 0) or 0),
            "tokens_out": int(usage.get("completion_tokens", 0) or 0),
            "tokens_total": int(usage.get("total_tokens", 0) or 0)}


def generate(prompt: str, *, system: Optional[str] = None, model: Optional[str] = None,
             temperature: float = 0.2, max_output_tokens: int = 700,
             purpose: str = "", retry: bool = True) -> Dict[str, Any]:
    """One real LLM call, or an honest 'no LLM available' envelope.

    Never raises: callers always get a JSON-safe dict with ``status``.
    """
    st = status()
    out: Dict[str, Any] = {
        "status": "ok" if st["available"] else "no_llm_available",
        "provider": st.get("provider", ""),
        "model": st.get("model", ""),
        "purpose": purpose,
        "tokens_in": 0, "tokens_out": 0, "tokens": 0,
        "latency_ms": 0.0, "text": "",
        "error": None,
    }
    if not st["available"]:
        out["error"] = st["reason"]
        return out

    # Gemma 4 26B A4B spends most of its output budget on internal reasoning, so
    # a tight cap can yield a valid call with ZERO output tokens (measured: a
    # 253-token prompt with cap=2048 returned 0 tokens after 46 s). Climb the
    # budget instead of reporting a false failure — every attempt's real token
    # usage is accumulated, nothing is hidden.
    attempts = [(model or st["model"], max_output_tokens)]
    if retry:
        for budget in (2048, 4096, 8192):
            if budget > max_output_tokens:
                attempts.append((model or st["model"], budget))
                break

    t0 = time.time()
    for i, (use_model, budget) in enumerate(attempts):
        try:
            if st["provider"] == "google":
                r = _generate_google(use_model, prompt, system,
                                     temperature, budget)
            else:
                r = _generate_openai(use_model, prompt, system,
                                     temperature, budget)
        except Exception as exc:
            out["status"] = "error"
            out["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:300])
            out["tokens_in"] = out["tokens_out"] = out["tokens"] = 0
            out["text"] = ""
            break
        # accumulate across attempts so no real token usage is hidden
        out["tokens_in"] = int(out.get("tokens_in") or 0) + int(r["tokens_in"])
        out["tokens_out"] = int(out.get("tokens_out") or 0) + int(r["tokens_out"])
        if r["text"]:
            out["text"] = r["text"]
            out["status"] = "ok"
            out["retried"] = i > 0
            out["max_output_tokens"] = budget
            break
        out["status"] = "empty_response"
        out["error"] = "provider returned no text (budget=%d)" % budget
    else:
        out["text"] = ""

    out["tokens"] = int(out.get("tokens_in") or 0) + int(out.get("tokens_out") or 0)
    out["latency_ms"] = round((time.time() - t0) * 1000, 1)
    return out


if __name__ == "__main__":
    print(json.dumps({"llm_status": status()}, indent=2))
    res = generate("Reply with the single word: ready", purpose="connectivity_probe")
    print(json.dumps({k: res[k] for k in
                      ("status", "provider", "model", "tokens", "tokens_in",
                       "tokens_out", "latency_ms", "error")}, indent=2))
    print("text:", (res.get("text") or "")[:200])
