import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests


class APIClient:
    def __init__(self, base_url: str, timeout_seconds: int = 60, max_retries: int = 4):
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.session = requests.Session()

    def request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        endpoint_override: Optional[str] = None,
    ) -> Any:
        url = endpoint_override or urljoin(self.base_url, endpoint.lstrip("/"))
        attempt = 0

        while True:
            attempt += 1
            response = self.session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=self.timeout_seconds,
            )

            if response.status_code in {429, 500, 502, 503, 504} and attempt <= self.max_retries:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 30)
                logging.warning(
                    "Transient API error status=%s attempt=%s url=%s wait=%ss",
                    response.status_code,
                    attempt,
                    url,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue

            if response.status_code >= 400:
                raise RuntimeError(
                    f"API request failed ({response.status_code}) at {url}. "
                    f"Response: {response.text[:2000]}"
                )

            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return response.json()

            try:
                return response.json()
            except ValueError:
                return {"raw_response": response.text}
