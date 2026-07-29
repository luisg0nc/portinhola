import base64
import json
import re
import shlex
from datetime import UTC, date, datetime
from urllib.parse import urlparse

from pydantic import BaseModel

ALLOWED_HOST = "balcaodigital.e-redes.pt"
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

_ANSI_C_ESCAPES = {"t": "\t", "n": "\n", "r": "\r", "\\": "\\", "'": "'", '"': '"'}


def _decode_ansi_c(inner: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            nxt = inner[i + 1]
            if nxt == "x" and i + 3 < len(inner):
                out.append(chr(int(inner[i + 2 : i + 4], 16)))
                i += 4
                continue
            out.append(_ANSI_C_ESCAPES.get(nxt, nxt))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _expand_ansi_c_quotes(text: str) -> str:
    # Chrome "Copy as cURL" uses $'...' (ANSI-C quoting) for args with
    # special bytes. shlex doesn't interpret it, so decode each span and
    # re-quote it as a plain shell string shlex.split can read back.
    def _repl(match: "re.Match[str]") -> str:
        return shlex.quote(_decode_ansi_c(match.group(1)))

    return re.sub(r"\$'((?:\\.|[^'\\])*)'", _repl, text)


class CurlRequest(BaseModel):
    method: str
    url: str
    headers: dict[str, str]
    cookies: dict[str, str]
    body: str | None = None


class CurlValidationError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _split_cookie_string(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for pair in raw.split(";"):
        stripped = pair.strip()
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            cookies[key.strip()] = value.strip()
    return cookies


def parse_curl(text: str) -> CurlRequest:
    cleaned = text.strip()
    if not cleaned.startswith("curl"):
        raise CurlValidationError("not_curl")
    cleaned = cleaned.replace("\\\n", " ")
    cleaned = _expand_ansi_c_quotes(cleaned)
    try:
        tokens = shlex.split(cleaned)
    except ValueError as exc:
        raise CurlValidationError("not_curl") from exc
    tokens = tokens[1:]  # drop leading "curl"

    url: str | None = None
    method: str | None = None
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    body: str | None = None

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-H", "--header") and i + 1 < len(tokens):
            key, _, value = tokens[i + 1].partition(":")
            if key.strip().lower() == "cookie":
                cookies.update(_split_cookie_string(value))
            else:
                headers[key.strip()] = value.strip()
            i += 2
        elif tok in ("-b", "--cookie") and i + 1 < len(tokens):
            cookies.update(_split_cookie_string(tokens[i + 1]))
            i += 2
        elif tok in ("-X", "--request") and i + 1 < len(tokens):
            method = tokens[i + 1].upper()
            i += 2
        elif tok in ("--data", "--data-raw", "--data-binary", "-d") and i + 1 < len(tokens):
            body = tokens[i + 1]
            i += 2
        elif tok.startswith("-"):
            i += 1  # valueless flag (--compressed, -s, --location, ...)
        else:
            if url is None:
                url = tok
            i += 1

    if url is None:
        raise CurlValidationError("not_curl")
    if method is None:
        method = "POST" if body is not None else "GET"
    return CurlRequest(method=method, url=url, headers=headers, cookies=cookies, body=body)


def validate(req: CurlRequest) -> None:
    host = urlparse(req.url).hostname or ""
    if host != ALLOWED_HOST:
        raise CurlValidationError("wrong_host")
    haystack = req.url + (req.body or "")
    if len(_ISO_DATE.findall(haystack)) < 2:
        raise CurlValidationError("no_date_range")


def read_expiry(req: CurlRequest) -> datetime | None:
    auth = next((v for k, v in req.headers.items() if k.lower() == "authorization"), "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1]
    parts = token.split(".")
    if len(parts) < 2:
        return None
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
        exp = claims.get("exp")
        if exp is None:
            return None
        return datetime.fromtimestamp(int(exp), tz=UTC)
    except (ValueError, json.JSONDecodeError):
        return None


def substitute_dates(req: CurlRequest, date_from: date, date_to: date) -> CurlRequest:
    # One shared counter across url THEN body: the first ISO date found
    # becomes date_from; every later date becomes date_to. Correct whether
    # dates live in the query string, the body, or split across both.
    replacements = [date_from.isoformat(), date_to.isoformat()]
    state = {"n": 0}

    def _repl(_m: "re.Match[str]") -> str:
        idx = 0 if state["n"] == 0 else 1
        state["n"] += 1
        return replacements[idx]

    new_url = _ISO_DATE.sub(_repl, req.url)
    new_body = _ISO_DATE.sub(_repl, req.body) if req.body else None
    return req.model_copy(update={"url": new_url, "body": new_body})
