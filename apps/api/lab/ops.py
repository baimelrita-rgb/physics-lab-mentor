"""Operations (MVP package 7): JSON error logs with a request id, optional alert webhook, health.

- Every response carries an X-Request-ID header. An unhandled error is written to stderr as one
  JSON line (time, request id, method, path, error, traceback) and the client gets a 500 with the
  request id only, so a teacher can quote it and the log line can be found.
- ERROR_WEBHOOK_URL (optional): each error is also POSTed there as JSON (at most one per minute),
  e.g. to a Slack/Teams incoming webhook or any error collector. No student text is sent: only
  the path, the error type and message, and the request id.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
import urllib.request
import uuid

STARTED = time.time()
_last_alert = 0.0
_alert_lock = threading.Lock()


def request_id() -> str:
    return uuid.uuid4().hex[:16]


def log(event: str, **fields):
    line = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **fields}
    print(json.dumps(line, ensure_ascii=False), file=sys.stderr, flush=True)


def report_error(rid: str, method: str, path: str, exc: BaseException):
    log("error", request_id=rid, method=method, path=path, error=type(exc).__name__, message=str(exc)[:500],
        traceback="".join(traceback.format_exception(exc))[-4000:])
    url = os.environ.get("ERROR_WEBHOOK_URL")
    if not url:
        return
    global _last_alert
    with _alert_lock:
        if time.time() - _last_alert < 60:
            return
        _last_alert = time.time()
    text = f"Lab mentor error {type(exc).__name__} on {method} {path} (request {rid})"
    body = json.dumps({"text": text, "request_id": rid, "path": path, "error": type(exc).__name__}).encode()

    def send():
        try:
            urllib.request.urlopen(urllib.request.Request(url, data=body, headers={"content-type": "application/json"}),
                                   timeout=5).close()
        except Exception as e:                     # alerting must never break the server
            log("alert_failed", error=type(e).__name__)
    threading.Thread(target=send, daemon=True).start()


def version() -> str:
    return os.environ.get("APP_VERSION", "dev")
