# Ghosh - API Test

Automated API tests for [PokeAPI](https://pokeapi.co), a free public REST API that needs no authentication.

Written in **Python** with **pytest**, **requests**, **jsonschema** and **responses** (for stubbing).

## Why PokeAPI

- No auth token, so anyone can clone and run the suite immediately.
- Read-only and backed by stable reference data (Pokedex numbers, base types), which lets live tests make exact assertions without becoming flaky.
- Supports single-resource lookups, pagination and linked resources, which gives a realistic surface to test.

## Project layout

```
api_client/
  pokeapi_client.py        Thin HTTP client: base URL, timeout, retry policy
tests/
  conftest.py              Fixtures: live client, stub client, schema validator
  schemas/                 JSON Schemas for response contracts
  test_pokemon_live.py     Tests against the real API
  test_pokemon_stubbed.py  Offline tests with mocked HTTP
.github/workflows/tests.yml  CI: stubbed tests, then live tests, plus a daily run
```

## Running the tests

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

pytest                  # everything
pytest -m "not live"    # offline only (no network needed)
pytest -m live          # real API only
pytest -m contract      # schema/contract checks only
```

Point the suite at another environment (a local mirror or staging) with:

```bash
POKEAPI_BASE_URL=https://my-mirror.example/api/v2 pytest -m live
```

## Test strategy

| Area | What is covered |
|---|---|
| Happy path | Lookup by name and by ID, expected IDs, types, height/weight, all six base stats |
| Contract | Response bodies validated against JSON Schemas (`pokemon`, `pokemon_list`) |
| Negative | Unknown name, ID 0, negative ID, out-of-range ID all return 404 |
| Pagination | `limit` honoured, first page has no `previous`, consecutive pages don't overlap, offset past the end returns an empty page |
| Consistency | ID and name lookups return the same resource; the `type/electric` endpoint lists Pikachu; every ability link a Pokemon references resolves |
| Non-functional | `Content-Type` is JSON; response time under a threshold |
| Resilience (stubbed) | 5xx surfaced not swallowed; transient 503 is retried then succeeds; retries stop after the limit; 404 is never retried; timeouts raise; malformed JSON raises |
| Client behaviour (stubbed) | Correct URL, `Accept` header and query params sent; unset params omitted; base URL configurable by env var |

### Design decisions

- **Live and stubbed tests are separated by marker.** Live tests prove the real API behaves as expected; stubbed tests cover failure modes the real API can't produce on demand (500s, timeouts, bad bodies) and run deterministically in CI with no network.
- **Assertions avoid volatile data.** The suite never asserts the total Pokemon count or anything that changes when new games add entries; it asserts on long-stable data and on relationships (`count > limit`, pages disjoint).
- **Retries only for transient errors.** The client retries 429/5xx with backoff so a blip in a public API doesn't fail the build, but never retries 4xx, so a genuine 404 is reported, not masked. After retries run out, the final response is returned so tests assert on the real status.
- **Schema tests guard both directions.** The stubbed payload is validated against the same schema as live data, and there are negative tests proving the schema rejects missing fields and wrong types, so the contract checks can't silently pass everything.
- **Parametrized cases** keep the suite compact and make each failing input show up by name in the report.

## Possible extensions

- Run in parallel with `pytest-xdist` and produce an HTML report with `pytest-html`.
- Record live responses once and replay them (VCR-style) to snapshot-test for unexpected changes.
- Add rate-limit and caching-header checks (`ETag`, `Cache-Control`).
