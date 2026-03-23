from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass(slots=True)
class HttpClient:
    timeout: int
    retries: int
    backoff: float
    rate_limit_sec: float
    user_agent: str
    session: requests.Session = field(init=False)

    def __post_init__(self) -> None:
        self.session = requests.Session()
        retry = Retry(
            total=self.retries,
            read=self.retries,
            connect=self.retries,
            status=self.retries,
            backoff_factor=self.backoff,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

    def get_text(self, url: str, params: dict | None = None) -> str:
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        # DCInside page is UTF-8; lock for deterministic parsing.
        response.encoding = "utf-8"
        self._sleep()
        return response.text

    def get_bytes(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        request_headers = headers or {}
        response = self.session.get(url, timeout=self.timeout, headers=request_headers)
        response.raise_for_status()
        self._sleep()
        return response.content

    def close(self) -> None:
        self.session.close()

    def _sleep(self) -> None:
        jitter = random.uniform(0.05, 0.25)
        time.sleep(max(0.0, self.rate_limit_sec + jitter))
