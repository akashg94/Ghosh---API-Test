"""Thin client for PokeAPI (https://pokeapi.co).

Keeping HTTP details here means tests describe behaviour, not plumbing,
and the base URL can be pointed at a stub or another environment.
"""
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_BASE_URL = "https://pokeapi.co/api/v2"
DEFAULT_TIMEOUT = 10  # seconds


class PokeApiClient:
    def __init__(self, base_url=None, timeout=DEFAULT_TIMEOUT, retries=3):
        self.base_url = (base_url or os.getenv("POKEAPI_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        # Retry only transient server/rate-limit errors, never 4xx client errors,
        # so a real 404 still surfaces as a test result rather than being masked.
        retry = Retry(
            total=retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "HEAD"),
            # Once retries run out, hand back the last response so callers and
            # tests can assert on the real status code instead of an exception.
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    def _url(self, path):
        return f"{self.base_url}/{path.lstrip('/')}"

    def request(self, method, path, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        return self.session.request(method, self._url(path), **kwargs)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def get_pokemon(self, name_or_id):
        return self.get(f"pokemon/{name_or_id}")

    def list_pokemon(self, limit=None, offset=None):
        params = {k: v for k, v in {"limit": limit, "offset": offset}.items() if v is not None}
        return self.get("pokemon", params=params)

    def get_type(self, name_or_id):
        return self.get(f"type/{name_or_id}")

    def get_ability(self, name_or_id):
        return self.get(f"ability/{name_or_id}")
