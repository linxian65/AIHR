"""PII scrubbing and audit log utilities."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_CARD_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def scrub_text(text: str) -> tuple[str, dict]:
    """Return (scrubbed_text, hit_counts). Mutates only when matches found."""
    hits = {"phone": 0, "id_card": 0, "email": 0}
    if not isinstance(text, str):
        return text, hits

    def _sub_phone(m):
        hits["phone"] += 1
        return "[手机号已脱敏]"

    def _sub_id(m):
        hits["id_card"] += 1
        return "[身份证已脱敏]"

    def _sub_email(m):
        hits["email"] += 1
        return "[邮箱已脱敏]"

    text = PHONE_RE.sub(_sub_phone, text)
    text = ID_CARD_RE.sub(_sub_id, text)
    text = EMAIL_RE.sub(_sub_email, text)
    return text, hits


def scrub_tool_input(tool_name: str, input_data: dict) -> tuple[dict, dict]:
    """Return (new_input_data, hit_counts).

    Only mutates Write.content and Edit.new_string. Other tools pass
    through unchanged — scanning is done by scan_pii_in_input for audit.
    """
    hits_total = {"phone": 0, "id_card": 0, "email": 0}
    if tool_name == "Write" and isinstance(input_data.get("content"), str):
        new_content, hits = scrub_text(input_data["content"])
        for k in hits_total:
            hits_total[k] += hits[k]
        if any(hits.values()):
            new_input = dict(input_data)
            new_input["content"] = new_content
            return new_input, hits_total
    elif tool_name == "Edit" and isinstance(input_data.get("new_string"), str):
        new_str, hits = scrub_text(input_data["new_string"])
        for k in hits_total:
            hits_total[k] += hits[k]
        if any(hits.values()):
            new_input = dict(input_data)
            new_input["new_string"] = new_str
            return new_input, hits_total
    return input_data, hits_total


def scan_pii_in_input(tool_name: str, input_data: dict) -> dict:
    """Recursively walk input_data, count PII matches in every string value.

    Tool-agnostic — used for audit on any tool. Scrubbed placeholders
    ('[手机号已脱敏]' etc.) don't match the regexes, so the count
    effectively reports PII that survived (i.e. in tools like send_email
    that we do not mutate).
    """
    hits = {"phone": 0, "id_card": 0, "email": 0}

    def _walk(value) -> None:
        if isinstance(value, str):
            hits["phone"] += len(PHONE_RE.findall(value))
            hits["id_card"] += len(ID_CARD_RE.findall(value))
            hits["email"] += len(EMAIL_RE.findall(value))
        elif isinstance(value, dict):
            for v in value.values():
                _walk(v)
        elif isinstance(value, list):
            for v in value:
                _walk(v)

    _walk(input_data)
    return hits


AUDIT_LOG = Path(__file__).resolve().parent.parent.parent / "workspace" / "audit.log.jsonl"


def write_audit(record: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def make_audit_record(
    session_id: str,
    tool_name: str,
    input_data: dict,
    decision: str,
    reason: str | None,
    pii_hits: dict,
) -> dict:
    payload = json.dumps(input_data, sort_keys=True, ensure_ascii=False)
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "tool_name": tool_name,
        "input_hash": hashlib.sha256(payload.encode()).hexdigest()[:16],
        "decision": decision,
        "reason": reason,
        "pii_hits": pii_hits,
    }
