"""Official REST only. Bounded memory cache, single-flight and global rate limit."""
import hashlib
import json
import socket
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from research.errors import ResearchError

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
MAX_RESPONSE = 12 * 1024 * 1024


@dataclass(frozen=True)
class Snapshot:
    body: bytes
    url: str
    fetched_at: str
    sha256: str
    cache_hit: bool = False

    def evidence(self):
        return {"provider": "Europe PMC", "url": self.url,
                "fetchedAt": self.fetched_at, "sha256": self.sha256,
                "cacheHit": self.cache_hit, "hashAlgorithm": "SHA-256"}


def network_transport(url):
    request = Request(url, headers={"User-Agent": "PaperResearchWorkbench/0.1 (local research prototype)",
                                    "Accept": "application/json, application/xml;q=0.9"})
    with urlopen(request, timeout=20) as response:
        body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE:
            raise ResearchError("RESPONSE_TOO_LARGE", "上游响应超过当前安全读取上限。")
        return body


class EuropePMC:
    def __init__(self, transport=network_transport, interval=1.0, ttl=900,
                 clock=time.monotonic, sleeper=time.sleep):
        self.transport, self.interval, self.ttl = transport, interval, ttl
        self.clock, self.sleeper = clock, sleeper
        self.cache = OrderedDict()
        self.cache_bytes = 0
        self.inflight = {}
        self.guard = threading.RLock()
        self.rate_guard = threading.Lock()
        self.next_request = 0.0
        self.network_calls = 0

    def _attempt(self, url):
        for attempt in range(3):
            retry_after = 0
            try:
                # Serialize starts globally: no more than 1 request/second by default.
                with self.rate_guard:
                    delay = self.next_request - self.clock()
                    if delay > 0:
                        self.sleeper(delay)
                    self.next_request = self.clock() + self.interval
                    self.network_calls += 1
                return self.transport(url)
            except HTTPError as exc:
                if exc.code == 404:
                    raise ResearchError("FULLTEXT_UNAVAILABLE", "来源没有提供可读取的全文，请查看原文。", 404) from exc
                if exc.code == 400:
                    raise ResearchError("INVALID_QUERY", "Europe PMC 未接受该查询式，请检查字段与括号。", 400) from exc
                if exc.code != 429 and exc.code < 500:
                    raise ResearchError("UPSTREAM_REJECTED", "来源暂时拒绝该请求，请稍后重试。") from exc
                raw = exc.headers.get("Retry-After", "0") if exc.headers else "0"
                try:
                    retry_after = max(0, float(raw))
                except ValueError:
                    try:
                        retry_after = max(0, parsedate_to_datetime(raw).timestamp() - time.time())
                    except (ValueError, TypeError, OverflowError):
                        retry_after = 0
                # Do not ignore a server request to wait longer; surface it for a later retry.
                if retry_after > 15:
                    raise ResearchError("UPSTREAM_RATE_LIMIT", "来源要求较长等待，请稍后手动重试。", 503) from exc
                last = exc
            except (URLError, TimeoutError, socket.timeout, OSError) as exc:
                last = exc
            if attempt < 2:
                self.sleeper(max(2 ** attempt, retry_after))
        raise ResearchError("UPSTREAM_UNAVAILABLE", "无法连接 Europe PMC，已有限重试。请检查网络后重试。", 503) from last

    def fetch(self, path, validator=None):
        url = BASE + path
        with self.guard:
            cached = self.cache.get(url)
            if cached and self.clock() - cached[0] < self.ttl:
                self.cache.move_to_end(url)
                s = cached[1]
                return Snapshot(s.body, s.url, s.fetched_at, s.sha256, True)
            if cached:
                self.cache_bytes -= len(cached[1].body)
                del self.cache[url]
            future = self.inflight.get(url)
            owner = future is None
            if owner:
                future = self.inflight[url] = Future()
        if not owner:
            return future.result(timeout=90)
        try:
            body = self._attempt(url)
            if validator:
                validator(body)  # Rejected full text never enters cache.
            s = Snapshot(body, url, datetime.now(timezone.utc).isoformat(), hashlib.sha256(body).hexdigest())
            with self.guard:
                self.cache[url] = (self.clock(), s)
                self.cache_bytes += len(body)
                while len(self.cache) > 24 or self.cache_bytes > 32 * 1024 * 1024:
                    _, (_, old) = self.cache.popitem(last=False)
                    self.cache_bytes -= len(old.body)
            future.set_result(s)
            return s
        except Exception as exc:
            future.set_exception(exc)
            # Mark it observed even when no other caller is awaiting it.
            future.exception()
            raise
        finally:
            with self.guard:
                self.inflight.pop(url, None)

    def search(self, query, page_size):
        path = "/search?" + urlencode({"query": query, "format": "json", "resultType": "core", "pageSize": page_size})
        snapshot = self.fetch(path)
        try:
            data = json.loads(snapshot.body)
            records = data["resultList"]["result"]
            if not isinstance(records, list) or any(not isinstance(p, dict) for p in records):
                raise ValueError("record shape")
            hit_count = int(data["hitCount"])
            if hit_count < 0:
                raise ValueError("hit count")
        except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
            raise ResearchError("INVALID_UPSTREAM_DATA", "来源返回格式异常，请稍后重试。") from exc
        return records, hit_count, snapshot, data.get("version", "unknown")

    def full_text(self, pmcid, validator):
        return self.fetch(f"/{pmcid}/fullTextXML", validator=validator)
