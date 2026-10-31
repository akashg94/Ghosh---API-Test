import json
import pathlib

import pytest
from jsonschema import Draft202012Validator

from api_client import PokeApiClient

SCHEMA_DIR = pathlib.Path(__file__).parent / "schemas"
STUB_BASE_URL = "https://stub.pokeapi.test/api/v2"


@pytest.fixture(scope="session")
def client():
    """Client for the real API (override with POKEAPI_BASE_URL)."""
    return PokeApiClient()


@pytest.fixture
def stub_client():
    """Client pointed at a fake host; retries off so failures are deterministic."""
    return PokeApiClient(base_url=STUB_BASE_URL, retries=0)


@pytest.fixture(scope="session")
def schema():
    cache = {}

    def _load(name):
        if name not in cache:
            cache[name] = json.loads((SCHEMA_DIR / f"{name}.json").read_text())
        return cache[name]

    return _load


@pytest.fixture(scope="session")
def assert_matches_schema(schema):
    def _assert(body, name):
        validator = Draft202012Validator(schema(name))
        errors = sorted(validator.iter_errors(body), key=lambda e: list(e.path))
        assert not errors, "Schema violations:\n" + "\n".join(
            f"  {'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors
        )

    return _assert
