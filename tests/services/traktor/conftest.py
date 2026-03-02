from pathlib import Path
import pytest
from plistsync.errors import DependencyError

try:
    from plistsync.services.traktor import NMLTrack
    from plistsync.services.traktor import NMLLibraryCollection
except DependencyError:
    pytest.skip("Traktor dependencies not installed", allow_module_level=True)


import lxml.etree as ET  # noqa: N812


@pytest.fixture
def collection(tmp_path: Path) -> NMLLibraryCollection:
    """Fixture to create a writable NMLCollection for testing.

    Copies the sample NML into a temp directory so tests can call .write()
    without modifying the repo fixture.
    """
    import shutil

    src = Path(__file__).parent.parent.parent / "data" / "traktor_playlist.nml"
    dest = tmp_path / "traktor_playlist.nml"
    shutil.copyfile(src, dest)
    return NMLLibraryCollection(dest)


@pytest.fixture
def sample_track():
    """Fixture to create a sample NMLTrack for testing."""
    return NMLTrack(
        ET.fromstring(
            """
                <ENTRY MODIFIED_DATE="2024/12/31" MODIFIED_TIME="84980"
                    AUDIO_ID="APd4yoypyZuaqbuMqM7+u+3f393+v/3IevqreJZFrv23u7zZvZzZunes/8itvNzv3//9r9///+/7///r///M7v//yvvP/v//////////////////////////////////////////////////////////3////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+///////////////////////////////////////////////////////////8lRAAAAAA=="
                    TITLE="Ready Or Not (Original Mix)" ARTIST="Smash, Grab">
                    <LOCATION DIR="/:sync/:jungle is massive/:" FILE="06 Ready Or Not [1074kbps].flac"
                        VOLUME="F:" VOLUMEID="6580a7aa"></LOCATION>
                    <ALBUM TRACK="6"
                        TITLE="Welcome To The Jungle, Vol. 5: The Ultimate Jungle Cakes Drum &amp; Bass Compilation"></ALBUM>
                    <MODIFICATION_INFO AUTHOR_TYPE="user"></MODIFICATION_INFO>
                    <INFO BITRATE="1075000" PRODUCER="Jungle Cakes"
                        COVERARTID="121/ZXLGDNDNMRPNLDS4GWDYBLD20QPA" KEY="8m" PLAYCOUNT="1" PLAYTIME="247"
                        IMPORT_DATE="2025/1/5" LAST_PLAYED="2025/1/1" RELEASE_DATE="2017/7/17" FLAGS="12"
                        FILESIZE="32703" COLOR="5"></INFO>
                    <TEMPO BPM="175.000031" BPM_QUALITY="100.000000"></TEMPO>
                    <LOUDNESS PEAK_DB="0.214146" PERCEIVED_DB="-3.563812" ANALYZED_DB="-3.563812"></LOUDNESS>
                    <MUSICAL_KEY VALUE="22"></MUSICAL_KEY>
                    <CUE_V2 NAME="AutoGrid" DISPL_ORDER="0" TYPE="4" START="2.342987" LEN="0.000000"
                        REPEATS="-1" HOTCUE="-1">
                        <GRID BPM="175.000031"></GRID>
                    </CUE_V2>
                    <CUE_V2 NAME="AutoGrid" DISPL_ORDER="0" TYPE="0" START="2.342987" LEN="0.000000"
                        REPEATS="-1" HOTCUE="0" COLOR="#FFFFFF"></CUE_V2>
                </ENTRY>
                """
        )
    )
