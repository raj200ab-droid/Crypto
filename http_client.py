"""Tiny HTTP helper built on the standard library (no `requests` needed)."""
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

_ctx_cache = {}


def _ssl_context():
    if "ctx" not in _ctx_cache:
        try:
            import certifi
            _ctx_cache["ctx"] = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            _ctx_cache["ctx"] = ssl.create_default_context()
    return _ctx_cache["ctx"]


def request_json(url, params=None, data=None, timeout=10):
    """Returns (status_code, parsed_json_or_None). Status 0 means network error."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    body = None
    headers = {"User-Agent": "CryptoScanner/1.0"}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw.decode("utf-8"))
            except ValueError:
                return resp.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def get_json(url, params=None, timeout=10):
    status, data = request_json(url, params=params, timeout=timeout)
    return data if status == 200 else None


def post_json(url, payload, timeout=10):
    status, _ = request_json(url, data=payload, timeout=timeout)
    return status == 200
