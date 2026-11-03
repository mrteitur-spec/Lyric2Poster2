from pathlib import Path
from io import BytesIO

from PIL import Image

from songposter.art_director import create_demo_brief
from songposter.charts import load_tracks
from songposter.image_engine import create_demo_artwork
from songposter.models import ArtBrief
from songposter.overlay import add_title_overlay
from songposter.safety import clean_lyrics


def test_lyrics_are_not_part_of_art_brief():
    canary = "PRIVATE_LYRIC_CANARY_94721"
    brief = create_demo_brief(
        title="Glass Horizon",
        artist="Mira Vale",
        lyrics=f"{canary} and a little light above the sea",
        style="Aurora",
    )
    serialized = repr(brief.to_dict())
    assert canary not in serialized
    assert "lyrics" not in brief.to_dict()


def test_clean_lyrics_normalizes_and_rejects_long_input():
    assert clean_lyrics("hello   world\n\n\nagain") == "hello world\n\nagain"
    try:
        clean_lyrics("x" * 20, max_chars=10)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected max character validation")


def test_demo_image_and_overlay_produce_png():
    brief = create_demo_brief(
        title="Paper Moons", artist="Juniper Echo", lyrics="dreams above the moonlit sky", style="Dreamscape"
    )
    background = create_demo_artwork(brief, size=(360, 540))
    poster = add_title_overlay(background, title="Paper Moons", artist="Juniper Echo", style=brief.style)
    output = BytesIO()
    poster.save(output, format="PNG")
    output.seek(0)
    with Image.open(output) as reopened:
        assert reopened.format == "PNG"
        assert reopened.size == (360, 540)


def test_sample_chart_is_available():
    chart_dir = Path(__file__).parents[1] / "data" / "charts"
    tracks = load_tracks(chart_dir)
    assert tracks
    assert {"title", "artist"}.issubset(tracks[0])


def test_brief_round_trip():
    brief = create_demo_brief(
        title="After the Static", artist="North Avenue", lyrics="rain and empty streets", style="Noir"
    )
    restored = ArtBrief.from_dict(brief.to_dict())
    assert restored == brief
