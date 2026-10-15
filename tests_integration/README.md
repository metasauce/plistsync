# Integration tests

Integration tests run against **live external services** with real credentials.
They exist to catch breaking API changes and other real-world issues that the
mocked unit tests under `tests/` cannot. They run on a schedule rather than on
every commit.

## Where

```
tests_integration/
├── abc/          # service-independent scenario and ordered tests
├── spotify/      # one package per service
└── tidal/
```

Each service package supplies a `scenario` fixture (its live library and a couple
of track identifiers) and subclasses `CollectionsTestBase`, which walks the
shared playlist lifecycle: look up tracks, create a playlist, edit it, add,
reorder and remove tracks, then delete it.

## Running

`testpaths = ["tests"]` keeps a plain `pytest` run from collecting these. Point
pytest at the directory explicitly:

```bash
uv run pytest tests_integration            # all services
uv run pytest tests_integration/spotify    # a single service
```

Configuration is read from the normal config directory (`PSYNC_CONFIG_DIR` or the
OS default). A service with a missing or invalid token is skipped with a hint, so
running locally is generally safe. Although not recommended to run with your
real accounts.

## Adding a service

Add `tests_integration/<service>/conftest.py` with the scenario:

```python
@pytest.fixture(scope="session")
def scenario() -> CollectionsScenario:
    return build_scenario(
        Library,
        Config,
        tracks=((<ServiceTrackID>("..."),), (<ServiceTrackID>("..."),)),
    )
```

and `tests_integration/<service>/test_collections.py`:

```python
class TestServiceCollections(CollectionsTestBase):
    """Runs the shared collections scenario against <Service>."""
```
