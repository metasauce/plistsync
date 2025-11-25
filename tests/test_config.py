from plistsync.errors import ConfigurationError
import pytest
import os
from plistsync.config import Config


@pytest.fixture
def temp_config_file(tmp_path):
    config_file = tmp_path / "config.yml"
    os.environ["PSYNC_CONFIG_DIR"] = str(tmp_path)
    return config_file, tmp_path


def test_create_default_config(temp_config_file):
    config = Config()
    assert os.path.exists(temp_config_file[0])

    # Default values from the schema
    assert config.path == temp_config_file[0]
    assert config.logging_level == "INFO"


class TestServiceConfig:
    @pytest.mark.parametrize("service", ["beets", "plex", "tidal", "spotify"])
    def test_service_not_enabled_by_default(self, temp_config_file, service):
        config = Config()
        assert os.path.exists(temp_config_file[0])
        with pytest.raises(ConfigurationError):
            getattr(config, service)

    @pytest.mark.parametrize(
        "service, config_data",
        [
            (
                "beets",
                (
                    "services:\n"
                    "    beets:\n"
                    "        enabled: true\n"
                    "        database: ./test.db"
                ),
            ),
            (
                "plex",
                (
                    "services:\n"
                    "    plex:\n"
                    "        enabled: true\n"
                    "        default_server_url: http://localhost:32400"
                ),
            ),
            (
                "tidal",
                (
                    "services:\n"
                    "    tidal:\n"
                    "        enabled: true\n"
                    "        client_id: testuser\n"
                ),
            ),
            (
                "spotify",
                (
                    "services:\n"
                    "    spotify:\n"
                    "        enabled: true\n"
                    "        client_id: testclientid\n"
                    "        redirect_port: 5001"
                ),
            ),
        ],
    )
    def test_enable_service_in_config(self, temp_config_file, service, config_data):
        config_data = "logging:\n    level: DEBUG\nredirect_port: 5000\n" + config_data
        print(config_data)
        temp_config_file[0].write_text(
            config_data,
            encoding="utf-8",
        )
        config = Config()
        assert os.path.exists(temp_config_file[0])
        service_config = getattr(config, service)
        assert service_config.enabled is True
