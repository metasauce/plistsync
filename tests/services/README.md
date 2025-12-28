# Testing services

Testing services should not require actual connections to external services. Instead, use mocking to simulate interactions with these services. This ensures that tests are reliable and do not depend on the availability of external systems.

Generally, services should have an API layer which allows to decouple the implementation from the actual service. This API layer can and should then be mocked in tests.


## Common patterns

Create a folder for each service under `tests/services/` (e.g. `tests/services/plex/`). Inside this folder, create test files for each component of the service (e.g. `test_track.py`, `test_collection.py`, etc.).

## ABCs for Services

To simplify testing common functionality across services, we provide Abstract Base Classes (ABCs) for services in the `tests.abc` which should be inherited in service tests.

- `TrackTestBase`: Base class for testing tracks
