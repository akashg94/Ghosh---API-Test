"""Offline tests using the `responses` library to stub HTTP.

These cover behaviour the live API can't produce on demand (server
errors, timeouts, malformed bodies) and verify that the client sends the
requests we expect. They run in CI with no network access.
"""
import pytest
import requests
import responses
from responses import matchers

from api_client import PokeApiClient
from tests.conftest import STUB_BASE_URL

pytestmark = pytest.mark.stubbed

PIKACHU = {
    "id": 25,
    "name": "pikachu",
    "height": 4,
    "weight": 60,
    "base_experience": 112,
    "types": [{"slot": 1, "type": {"name": "electric", "url": f"{STUB_BASE_URL}/type/13/"}}],
    "abilities": [
        {"ability": {"name": "static", "url": f"{STUB_BASE_URL}/ability/9/"}, "is_hidden": False, "slot": 1},
    ],
    "stats": [
        {"base_stat": v, "stat": {"name": n, "url": f"{STUB_BASE_URL}/stat/{i}/"}}
        for i, (n, v) in enumerate(
            [("hp", 35), ("attack", 55), ("defense", 40),
             ("special-attack", 50), ("special-defense", 50), ("speed", 90)],
            start=1,
        )
    ],
    "sprites": {},
}


@responses.activate
def test_client_requests_expected_url_and_headers(stub_client):
    responses.get(
        f"{STUB_BASE_URL}/pokemon/pikachu",
        json=PIKACHU,
        match=[matchers.header_matcher({"Accept": "application/json"})],
    )

    response = stub_client.get_pokemon("pikachu")

    assert response.status_code == 200
    assert response.json()["id"] == 25
    assert len(responses.calls) == 1


@responses.activate
def test_list_sends_pagination_params(stub_client):
    responses.get(
        f"{STUB_BASE_URL}/pokemon",
        json={"count": 2, "next": None, "previous": None, "results": []},
        match=[matchers.query_param_matcher({"limit": "2", "offset": "10"})],
    )

    response = stub_client.list_pokemon(limit=2, offset=10)

    assert response.status_code == 200


@responses.activate
def test_list_omits_unset_params(stub_client):
    responses.get(
        f"{STUB_BASE_URL}/pokemon",
        json={"count": 0, "next": None, "previous": None, "results": []},
        match=[matchers.query_param_matcher({})],
    )

    assert stub_client.list_pokemon().status_code == 200


@pytest.mark.contract
@responses.activate
def test_stubbed_payload_satisfies_schema(stub_client, assert_matches_schema):
    """Guards the fixture itself: if the schema changes, the stub must too."""
    responses.get(f"{STUB_BASE_URL}/pokemon/pikachu", json=PIKACHU)

    assert_matches_schema(stub_client.get_pokemon("pikachu").json(), "pokemon")


@pytest.mark.contract
def test_schema_rejects_missing_required_field(assert_matches_schema):
    broken = {k: v for k, v in PIKACHU.items() if k != "types"}

    with pytest.raises(AssertionError, match="types"):
        assert_matches_schema(broken, "pokemon")


@pytest.mark.contract
def test_schema_rejects_wrong_field_type(assert_matches_schema):
    broken = {**PIKACHU, "id": "25"}

    with pytest.raises(AssertionError, match="id"):
        assert_matches_schema(broken, "pokemon")


@pytest.mark.parametrize("status", [500, 502, 503])
@responses.activate
def test_server_errors_are_surfaced_not_swallowed(stub_client, status):
    responses.get(f"{STUB_BASE_URL}/pokemon/pikachu", status=status)

    response = stub_client.get_pokemon("pikachu")

    assert response.status_code == status
    assert not response.ok


@responses.activate
def test_client_retries_transient_503_then_succeeds():
    client_with_retry = PokeApiClient(base_url=STUB_BASE_URL, retries=2)
    client_with_retry.session.adapters["https://"].max_retries.backoff_factor = 0

    url = f"{STUB_BASE_URL}/pokemon/pikachu"
    responses.get(url, status=503)
    responses.get(url, json=PIKACHU, status=200)

    response = client_with_retry.get_pokemon("pikachu")

    assert response.status_code == 200
    assert len(responses.calls) == 2


@responses.activate
def test_client_does_not_retry_404():
    client_with_retry = PokeApiClient(base_url=STUB_BASE_URL, retries=3)
    responses.get(f"{STUB_BASE_URL}/pokemon/missingno", status=404, body="Not Found")

    response = client_with_retry.get_pokemon("missingno")

    assert response.status_code == 404
    assert len(responses.calls) == 1


@responses.activate
def test_timeout_raises(stub_client):
    responses.get(
        f"{STUB_BASE_URL}/pokemon/pikachu",
        body=requests.exceptions.ConnectTimeout("simulated timeout"),
    )

    with pytest.raises(requests.exceptions.ConnectTimeout):
        stub_client.get_pokemon("pikachu")


@responses.activate
def test_malformed_json_raises_decode_error(stub_client):
    responses.get(
        f"{STUB_BASE_URL}/pokemon/pikachu",
        body="<html>gateway error</html>",
        content_type="text/html",
    )

    response = stub_client.get_pokemon("pikachu")

    with pytest.raises(requests.exceptions.JSONDecodeError):
        response.json()


def test_default_timeout_is_applied():
    assert PokeApiClient().timeout > 0


def test_base_url_can_be_overridden_by_env(monkeypatch):
    monkeypatch.setenv("POKEAPI_BASE_URL", "https://staging.example.test/api/v2/")

    assert PokeApiClient().base_url == "https://staging.example.test/api/v2"


@responses.activate
def test_client_returns_last_response_when_retries_exhausted():
    client_with_retry = PokeApiClient(base_url=STUB_BASE_URL, retries=2)
    client_with_retry.session.adapters["https://"].max_retries.backoff_factor = 0
    responses.get(f"{STUB_BASE_URL}/pokemon/pikachu", status=503)

    response = client_with_retry.get_pokemon("pikachu")

    assert response.status_code == 503
    assert len(responses.calls) == 3  # 1 original attempt + 2 retries
