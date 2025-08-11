import os
import pytest

try:
    from mutagen._file import File as MutagenFile
    from tinytag import TinyTag
    from taglib import File as TagLibFile
    from music_tag import load_file as music_tag_load_file
except ImportError:
    pytest.skip(
        "Skipping benchmarks, install dep with pip install .[bench]",
        allow_module_level=True,
    )


TEST_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_files"))


# Fixture to get a list of all the files in the test_files directory
@pytest.fixture
def audio_files():
    files = [f for f in os.listdir(TEST_PATH) if f.endswith((".mp3", ".flac", ".wav"))]

    if len(files) == 0:
        pytest.skip("No audio files found in test_files directory")

    return files


def test_readtags_tinytag(benchmark, audio_files):
    def run():
        for file in audio_files:
            tag = TinyTag.get(f"{TEST_PATH}/{file}")
            tags_dict = {key: value for key, value in tag.as_dict().items()}

    benchmark(run)


def test_readtags_mutagen(benchmark, audio_files):
    def run():
        for file in audio_files:
            m_f = MutagenFile(f"{TEST_PATH}/{file}", easy=True)
            tags_dict = {key: value for key, value in m_f.tags.items()}  # type: ignore

    benchmark(run)


def test_readtags_taglib(benchmark, audio_files):
    def run():
        for file in audio_files:
            f = TagLibFile(f"{TEST_PATH}/{file}")
            tags_dict = f.tags

    benchmark(run)


# Wrapper around mutagen (should have very similar performance)
def test_readtags_music_tag(benchmark, audio_files):
    def run():
        for file in audio_files:
            song = music_tag_load_file(f"{TEST_PATH}/{file}")
            tags_dict = {key: value for key, value in song.__dict__.items()}

    benchmark(run)
