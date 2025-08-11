from plistsync.errors import ConfigurationError, MultiConfigurationError
import pytest
import os


@pytest.fixture
def temp_config_file(tmp_path):
    config_file = tmp_path / "config.yml"
    os.environ["PSYNC_CONFIG_DIR"] = str(tmp_path)
    return config_file, tmp_path


def test_create_default_config(temp_config_file):
    from plistsync.config.yaml import Config

    config = Config()
    assert os.path.exists(temp_config_file[0])

    # Default values from the schema
    assert config.path == temp_config_file[0]
    assert config.logging_level == "INFO"

    # Default raise ConfigurationError if not set
    with pytest.raises(ConfigurationError):
        config.beets
    with pytest.raises(ConfigurationError):
        config.plex
    with pytest.raises(ConfigurationError):
        config.tidal


def test_error_in_schema(temp_config_file):
    from plistsync.config.yaml import Config

    temp_config_file[0].write_text(
        """
        beets: bar
        """,
        encoding="utf-8",
    )
    with pytest.raises(MultiConfigurationError):
        c = Config()


def test_refresh_config(temp_config_file):
    from plistsync.config.yaml import Config

    config = Config()
    assert os.path.exists(temp_config_file[0])

    with open(temp_config_file[0], "w") as f:
        f.write("beets:\n    enabled: true\n    database: ./other.db\n")
    config.refresh()
    assert config.beets.database == "./other.db"  # type: ignore
