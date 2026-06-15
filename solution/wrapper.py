"""Thread-safe observability and mitigation around the opaque agent."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import time
import unicodedata

from telemetry.cost import cost_from_usage
from telemetry.logger import logger, new_correlation_id, set_correlation_id
from telemetry.redact import redact, redact_value


_RECOVERABLE_STATUSES = {"loop", "max_steps", "no_action", "wrapper_error"}
_TOOL_FIELDS = ("tool", "tool_name", "action", "name")
_NOTE_BLOCK = re.compile(
    r"\s+(?:ghi\s*ch[uú]|order\s+notes?|notes?)\s*[:\-]\s*.*$",
    re.IGNORECASE | re.DOTALL,
)
_CONTACT_BLOCK = re.compile(
    r"\s*(?:[,.?;:]?\s*(?:li[eê]n\s*h[eệ]|g[oọ]i\s*(?:m[iì]nh)?\s*qua)\s*)?"
    r"(?:email\s*)?[\w.+-]+@[\w-]+\.[\w.-]+"
    r"|\s*(?:[,.?;:]?\s*(?:li[eê]n\s*h[eệ]|g[oọ]i\s*(?:m[iì]nh)?\s*qua)\s*)?"
    r"(?:sdt|sđt|phone)?\s*(?:\+84|0)\d{9}\b",
    re.IGNORECASE,
)
_REDACTED_CONTACT = re.compile(
    r"\s*\([^)]*(?:li[eê]n\s*h[eệ]|contact)[^)]*\[REDACTED(?::[^]]+)?\][^)]*\)",
    re.IGNORECASE,
)
_COUPON_REQUEST = re.compile(r"\b(?:coupon|m[aã]\s*gi[aả]m|d[uù]ng\s*m[aã]|[aá]p\s*d[uụ]ng\s*m[aã])\b", re.IGNORECASE)
_DESTINATION_REQUEST = re.compile(r"\b(?:ship|giao)\b", re.IGNORECASE)
_TOTAL_REQUEST = re.compile(r"\b(?:t[oổ]ng|thanh\s*to[aá]n|t[ií]nh\s*ti[eề]n)\b", re.IGNORECASE)
_SUCCESS_TOTAL = re.compile(r"Tong cong:\s*\d+\s*VND", re.IGNORECASE)
_UNAVAILABLE = re.compile(
    r"(?:kh[oô]ng\s+(?:c[oó]\s+s[aẵ]n|kh[aả]\s*d[uụ]ng|đ[uủ]|the\s+requested)|ch[iỉ]\s+c[oò]n\s+\d+|h[eế]t\s+h[aà]ng|out\s+of\s+stock|not\s+available|cannot\s+(?:process|provide|calculate)|kh[oô]ng\s+th[eể])",
    re.IGNORECASE,
)


def _normalized_question(question):
    text = unicodedata.normalize("NFC", str(question or ""))
    return re.sub(r"\s+", " ", text).strip()


def _sanitize_question(question):
    """Remove appended order-note instructions while preserving the order itself."""
    normalized = _normalized_question(question)
    sanitized, note_count = _NOTE_BLOCK.subn("", normalized)
    sanitized, contact_count = _CONTACT_BLOCK.subn("", sanitized)
    return sanitized.strip(" ,.;"), note_count > 0, contact_count > 0


def _validation_reason(question, result):
    """Return a generic completeness failure that is worth one retry."""
    meta = result.get("meta") or {}
    tools = {str(tool).lower() for tool in meta.get("tools_used", [])}
    answer = str(result.get("answer") or "")
    if "check_stock" not in tools:
        return "missing_check_stock"
    if _UNAVAILABLE.search(answer):
        return None
    if _COUPON_REQUEST.search(question) and "get_discount" not in tools:
        return "missing_get_discount"
    if _DESTINATION_REQUEST.search(question) and "calc_shipping" not in tools:
        return "missing_calc_shipping"
    if _TOTAL_REQUEST.search(question) and not _SUCCESS_TOTAL.search(answer):
        return "missing_final_total"
    return None


def _cache_key(question, config):
    identity = {
        "question": _normalized_question(question),
        "model": config.get("model"),
        "prompt": config.get("system_prompt") or config.get("prompt_file"),
    }
    raw = json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "observathon:" + hashlib.sha256(raw).hexdigest()


def _trace_summary(trace):
    """Keep useful diagnostics without logging full prompts or tool payloads."""
    summary = []
    for step in trace or []:
        if not isinstance(step, dict):
            continue
        item = {}
        for field in _TOOL_FIELDS:
            if step.get(field):
                item["action"] = str(step[field])
                break
        if step.get("error"):
            item["error"] = str(step["error"])
        if item:
            summary.append(item)
    return summary[:20]


def _repeated_actions(summary):
    actions = [item.get("action") for item in summary if item.get("action")]
    return sorted({action for action in actions if actions.count(action) > 1})


def _safe_result(result):
    cleaned = copy.deepcopy(result if isinstance(result, dict) else {})
    answer, redactions = redact(cleaned.get("answer"))
    cleaned["answer"] = answer
    if isinstance(cleaned["answer"], str):
        cleaned["answer"] = _REDACTED_CONTACT.sub("", cleaned["answer"]).rstrip()
    cleaned.setdefault("status", "wrapper_error")
    cleaned.setdefault("steps", 0)
    cleaned.setdefault("trace", [])
    cleaned.setdefault("meta", {})
    cleaned["meta"] = dict(cleaned["meta"] or {})
    cleaned["meta"]["wrapper_pii_redactions"] = redactions
    return cleaned


def _log_result(result, context, wall_ms, attempts, cache_hit):
    meta = result.get("meta") or {}
    usage = meta.get("usage") or {}
    summary = _trace_summary(result.get("trace"))
    logger.log_event("AGENT_CALL", redact_value({
        "qid": context.get("qid"),
        "session_id": context.get("session_id"),
        "turn_index": context.get("turn_index"),
        "status": result.get("status"),
        "steps": result.get("steps"),
        "wall_ms": wall_ms,
        "reported_latency_ms": meta.get("latency_ms"),
        "provider": meta.get("provider"),
        "model": meta.get("model"),
        "usage": usage,
        "cost_usd": cost_from_usage(meta.get("model", ""), usage),
        "tools_used": meta.get("tools_used", []),
        "trace_summary": summary,
        "repeated_actions": _repeated_actions(summary),
        "attempts": attempts,
        "cache_hit": cache_hit,
        "pii_redactions": meta.get("wrapper_pii_redactions", 0),
        "wrapper_exception": meta.get("wrapper_exception"),
        "wrapper_error": meta.get("wrapper_error"),
        "input_sanitized": meta.get("wrapper_input_sanitized", False),
        "contact_removed": meta.get("wrapper_contact_removed", False),
        "validation_retries": meta.get("wrapper_validation_retries", []),
    }))


def mitigate(call_next, question, config, context):
    set_correlation_id(str(context.get("qid") or new_correlation_id()))
    conf = dict(config)
    safe_question, input_sanitized, contact_removed = _sanitize_question(question)
    key = _cache_key(safe_question, conf)
    cache = context.get("cache")
    lock = context.get("cache_lock")

    if cache is not None and lock is not None:
        with lock:
            cached = cache.get(key)
        if cached is not None:
            result = copy.deepcopy(cached)
            result.setdefault("meta", {})["wrapper_cache_hit"] = True
            result["meta"]["wrapper_input_sanitized"] = input_sanitized
            result["meta"]["wrapper_contact_removed"] = contact_removed
            _log_result(result, context, 0, 0, True)
            return result

    retry_conf = conf.get("retry") or {}
    max_attempts = max(1, min(int(retry_conf.get("max_attempts", 1)), 2))
    backoff_ms = max(0, int(retry_conf.get("backoff_ms", 0)))
    started = time.perf_counter()
    attempts = 0
    result = None
    validation_retries = []

    while attempts < max_attempts:
        attempts += 1
        try:
            result = _safe_result(call_next(safe_question, conf))
        except Exception as exc:
            result = _safe_result({
                "answer": None,
                "status": "wrapper_error",
                "meta": {
                    "wrapper_exception": type(exc).__name__,
                    "wrapper_error": str(exc)[:300],
                },
            })
        validation_reason = None
        if result.get("status") == "ok":
            validation_reason = _validation_reason(safe_question, result)
            if validation_reason:
                validation_retries.append(validation_reason)
        if result.get("status") not in _RECOVERABLE_STATUSES and not validation_reason:
            break
        if attempts < max_attempts and backoff_ms:
            time.sleep(backoff_ms / 1000.0)

    wall_ms = int((time.perf_counter() - started) * 1000)
    result["meta"]["wrapper_attempts"] = attempts
    result["meta"]["wrapper_cache_hit"] = False
    result["meta"]["wrapper_input_sanitized"] = input_sanitized
    result["meta"]["wrapper_contact_removed"] = contact_removed
    result["meta"]["wrapper_validation_retries"] = validation_retries

    if result.get("status") == "ok" and cache is not None and lock is not None:
        with lock:
            cache[key] = copy.deepcopy(result)

    _log_result(result, context, wall_ms, attempts, False)
    return result
