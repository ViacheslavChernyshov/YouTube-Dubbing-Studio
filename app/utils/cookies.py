"""
Helpers for normalizing cookie exports into Netscape cookies.txt format.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CookieNormalizationResult:
    netscape_text: str
    source_format: str


def is_netscape_cookie_text(text: str) -> bool:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# Netscape HTTP Cookie File"):
            return True
        if line.startswith("#"):
            continue
        if raw_line.count("\t") >= 6:
            return True
    return False


def extract_cookie_header(text: str) -> str:
    parts = [line.strip() for line in text.splitlines() if line.strip()]
    if not parts:
        return ""
    candidate = "".join(parts)
    if candidate.lower().startswith("cookie:"):
        candidate = candidate.split(":", 1)[1].strip()
    if candidate.lstrip().startswith(("{", "[")):
        return ""
    if "\t" in candidate or "=" not in candidate:
        return ""
    chunks = [chunk.strip() for chunk in candidate.split(";") if chunk.strip()]
    if not chunks or any("=" not in chunk for chunk in chunks):
        return ""
    return candidate


def extract_json_cookie_entries(text: str) -> list[dict[str, object]]:
    try:
        payload = json.loads(text)
    except Exception:
        return []

    if isinstance(payload, dict):
        for key in ("cookies", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                payload = value
                break
        else:
            return []

    if not isinstance(payload, list):
        return []

    entries: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            return []

        name = str(item.get("name") or "").strip()
        if not name:
            continue

        entries.append(
            {
                "domain": str(item.get("domain") or ".youtube.com").strip() or ".youtube.com",
                "hostOnly": bool(item.get("hostOnly", False)),
                "httpOnly": bool(item.get("httpOnly", False)),
                "name": name,
                "path": str(item.get("path") or "/").strip() or "/",
                "secure": bool(item.get("secure", False)),
                "session": bool(item.get("session", False)),
                "expirationDate": item.get("expirationDate", 0),
                "value": str(item.get("value") or ""),
            }
        )

    return entries


def convert_cookie_header_to_netscape(cookie_header: str) -> str:
    lines = [
        "# Netscape HTTP Cookie File",
        "# Auto-converted from a raw Cookie header for yt-dlp",
    ]
    for item in cookie_header.split(";"):
        chunk = item.strip()
        if not chunk or "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        lines.append(f".youtube.com\tTRUE\t/\tTRUE\t0\t{name}\t{value}")
    return "\n".join(lines) + "\n"


def convert_json_cookies_to_netscape(cookie_entries: list[dict[str, object]]) -> str:
    lines = [
        "# Netscape HTTP Cookie File",
        "# Auto-converted from a JSON cookie export for yt-dlp",
    ]
    for item in cookie_entries:
        domain = str(item.get("domain") or ".youtube.com").strip() or ".youtube.com"
        host_only = bool(item.get("hostOnly", False))
        if host_only:
            domain = domain.lstrip(".")
        elif not domain.startswith("."):
            domain = "." + domain

        path = str(item.get("path") or "/").strip() or "/"
        secure = "TRUE" if bool(item.get("secure", False)) else "FALSE"
        include_subdomains = "FALSE" if host_only else "TRUE"
        session = bool(item.get("session", False))
        expires_raw = item.get("expirationDate", 0)
        try:
            expires = 0 if session else int(float(expires_raw or 0))
        except Exception:
            expires = 0

        line_domain = f"#HttpOnly_{domain}" if bool(item.get("httpOnly", False)) else domain
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "")
        lines.append(
            f"{line_domain}\t{include_subdomains}\t{path}\t{secure}\t{expires}\t{name}\t{value}"
        )

    return "\n".join(lines) + "\n"


def normalize_cookie_text(text: str) -> CookieNormalizationResult | None:
    if not text.strip():
        return None
    if is_netscape_cookie_text(text):
        normalized = text if text.endswith("\n") else text + "\n"
        return CookieNormalizationResult(normalized, "netscape")

    cookie_header = extract_cookie_header(text)
    if cookie_header:
        return CookieNormalizationResult(
            convert_cookie_header_to_netscape(cookie_header),
            "header",
        )

    json_entries = extract_json_cookie_entries(text)
    if json_entries:
        return CookieNormalizationResult(
            convert_json_cookies_to_netscape(json_entries),
            "json",
        )

    return None


def save_normalized_cookie_text(text: str, destination: str | Path) -> CookieNormalizationResult:
    result = normalize_cookie_text(text)
    if result is None:
        raise ValueError(
            "Unsupported cookies format. Expected Netscape cookies.txt, raw Cookie header, or JSON export."
        )

    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(result.netscape_text, encoding="utf-8")
    return result
