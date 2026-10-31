"""Live tests against the real PokeAPI.

These assert on behaviour and on long-stable reference data (Pokedex
numbers, base types and sizes for original-generation Pokemon) rather
than on volatile values such as total counts.
"""
import pytest

pytestmark = pytest.mark.live

MAX_RESPONSE_SECONDS = 5


# --- Happy path: single resource ------------------------------------------

@pytest.mark.parametrize(
    "name, expected_id, expected_types",
    [
        ("bulbasaur", 1, ["grass", "poison"]),
        ("charizard", 6, ["fire", "flying"]),
        ("pikachu", 25, ["electric"]),
        ("mewtwo", 150, ["psychic"]),
    ],
)
def test_get_pokemon_by_name_returns_expected_data(client, name, expected_id, expected_types):
    response = client.get_pokemon(name)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == expected_id
    assert body["name"] == name
    # Sort by slot so the assertion is order-independent of the response list.
    types = [t["type"]["name"] for t in sorted(body["types"], key=lambda t: t["slot"])]
    assert types == expected_types


def test_get_pokemon_returns_json_content_type(client):
    response = client.get_pokemon("pikachu")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/json")


def test_get_pokemon_responds_within_threshold(client):
    response = client.get_pokemon("pikachu")

    assert response.status_code == 200
    assert response.elapsed.total_seconds() < MAX_RESPONSE_SECONDS


def test_lookup_by_id_and_by_name_return_same_resource(client):
    by_id = client.get_pokemon(25)
    by_name = client.get_pokemon("pikachu")

    assert by_id.status_code == by_name.status_code == 200
    assert by_id.json()["id"] == by_name.json()["id"]
    assert by_id.json()["name"] == by_name.json()["name"]


def test_pikachu_physical_attributes(client):
    body = client.get_pokemon("pikachu").json()

    # PokeAPI units: height in decimetres, weight in hectograms.
    assert body["height"] == 4
    assert body["weight"] == 60


def test_pokemon_has_all_six_base_stats(client):
    body = client.get_pokemon("pikachu").json()

    stat_names = {s["stat"]["name"] for s in body["stats"]}
    assert stat_names == {
        "hp", "attack", "defense", "special-attack", "special-defense", "speed",
    }
    assert all(s["base_stat"] > 0 for s in body["stats"])


@pytest.mark.contract
@pytest.mark.parametrize("name", ["bulbasaur", "pikachu", "ditto"])
def test_pokemon_response_matches_schema(client, assert_matches_schema, name):
    response = client.get_pokemon(name)

    assert response.status_code == 200
    assert_matches_schema(response.json(), "pokemon")


# --- Negative cases -------------------------------------------------------

@pytest.mark.parametrize(
    "identifier",
    ["not-a-real-pokemon", "0", "-1", "99999999"],
    ids=["unknown-name", "zero-id", "negative-id", "out-of-range-id"],
)
def test_get_unknown_pokemon_returns_404(client, identifier):
    response = client.get_pokemon(identifier)

    assert response.status_code == 404


# --- Collections and pagination -------------------------------------------

@pytest.mark.contract
def test_list_pokemon_matches_schema(client, assert_matches_schema):
    response = client.list_pokemon(limit=5)

    assert response.status_code == 200
    assert_matches_schema(response.json(), "pokemon_list")


@pytest.mark.parametrize("limit", [1, 5, 20])
def test_list_pokemon_honours_limit(client, limit):
    body = client.list_pokemon(limit=limit).json()

    assert len(body["results"]) == limit
    assert body["count"] > limit


def test_first_page_has_no_previous_and_has_next(client):
    body = client.list_pokemon(limit=10, offset=0).json()

    assert body["previous"] is None
    assert body["next"] is not None
    assert body["results"][0]["name"] == "bulbasaur"


def test_consecutive_pages_do_not_overlap(client):
    first = client.list_pokemon(limit=10, offset=0).json()["results"]
    second = client.list_pokemon(limit=10, offset=10).json()["results"]

    first_names = {p["name"] for p in first}
    second_names = {p["name"] for p in second}
    assert first_names.isdisjoint(second_names)


def test_offset_beyond_count_returns_empty_results(client):
    count = client.list_pokemon(limit=1).json()["count"]

    body = client.list_pokemon(limit=10, offset=count + 100).json()
    assert body["results"] == []
    assert body["next"] is None


# --- Cross-resource consistency -------------------------------------------

def test_type_endpoint_lists_pokemon_of_that_type(client):
    response = client.get_type("electric")

    assert response.status_code == 200
    members = {entry["pokemon"]["name"] for entry in response.json()["pokemon"]}
    assert "pikachu" in members


def test_pokemon_ability_links_resolve(client):
    body = client.get_pokemon("pikachu").json()

    for entry in body["abilities"]:
        name = entry["ability"]["name"]
        ability = client.get_ability(name)
        assert ability.status_code == 200, f"ability {name!r} did not resolve"
        assert ability.json()["name"] == name
