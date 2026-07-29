import shlex

from pydantic import BaseModel


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
