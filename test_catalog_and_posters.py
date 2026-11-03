from io import BytesIO

import pytest
from PIL import Image

from songposter.art_director import create_brief_for_song, create_demo_brief, infer_motifs
from songposter.catalog import filter_songs, genres, load_catalog
from songposter.models import ArtBrief
from songposter.overlay import add_title_overlay
from songposter.scene_engine import MOTIFS, create_scene_artwork
from songposter.styles import KNOWN_MOTIFS, MATCH_SONG, STYLE_PRESETS

CATALOG = load_catalog()


def test_catalog_is_large_and_valid():
    assert len(CATALOG) >= 30
    ids = [s.id for s in CATALOG]
    assert len(ids) == len(set(ids)), "song ids must be unique"
    for s in CATALOG:
        assert s.title and s.artist
        assert s.motifs and all(m in KNOWN_MOTIFS for m in s.motifs)
        assert len(s.palette) == 4
        assert s.style in STYLE_PRESETS


def test_only_public_domain_songs_carry_lyrics():
    for s in CATALOG:
        if s.lyrics:
            assert s.public_domain, f"{s.title} must not ship lyrics"
    assert any(s.public_domain for s in CATALOG)


def test_every_known_motif_has_a_renderer():
    assert set(KNOWN_MOTIFS) == set(MOTIFS)


def test_filter_and_genres():
    assert "K-Pop" in genres(CATALOG)
    kpop = filter_songs(CATALOG, genre="K-Pop")
    assert kpop and all(s.genre == "K-Pop" for s in kpop)
    assert [s.title for s in filter_songs(CATALOG, query="  blinding ")] == ["Blinding Lights"]
    assert filter_songs(CATALOG, query="zzzz-not-a-song") == []


def test_brief_for_catalog_song_is_lyric_free_and_seeded():
    song = next(s for s in CATALOG if s.id == "blinding-lights")
    brief = create_brief_for_song(song)
    assert brief.scene_motifs == list(song.motifs)
    assert brief.palette == list(song.palette)
    assert brief.seed == "Blinding Lights|The Weeknd"
    assert "lyrics" not in brief.to_dict()
    assert create_brief_for_song(song, variation=2).seed.endswith("#2")
    assert ArtBrief.from_dict(brief.to_dict()) == brief


def test_look_override_uses_style_palette():
    song = CATALOG[0]
    brief = create_brief_for_song(song, style="Noir")
    assert brief.style == "Noir" and brief.palette == STYLE_PRESETS["Noir"]["palette"]
    assert create_brief_for_song(song, style=MATCH_SONG).style == song.style


def test_infer_motifs_uses_keywords_and_whole_words():
    assert "waves" in infer_motifs("walking by the ocean", "introspective")
    assert "road" not in infer_motifs("I care about you", "introspective")  # "car" must not match "care"
    assert len(infer_motifs("", "hopeful")) == 2


def test_custom_song_can_use_mood_without_lyrics():
    brief = create_demo_brief(title="A", artist="B", mood="energetic")
    assert brief.mood == "energetic" and brief.scene_motifs
    with pytest.raises(ValueError):
        create_demo_brief(title="A", artist="B")


@pytest.mark.parametrize("motif", sorted(MOTIFS))
def test_each_motif_renders_at_requested_size(motif):
    brief = ArtBrief("c", "d", "m", [], ["#101020", "#304080", "#c04060", "#ffe0b0"], "Aurora", [motif, "stars"], "t")
    img = create_scene_artwork(brief, size=(240, 360), scale=1)
    assert img.size == (240, 360) and img.mode == "RGB"


def test_artwork_is_repeatable_and_differs_by_song():
    a, b = CATALOG[0], CATALOG[1]
    one = create_scene_artwork(create_brief_for_song(a), size=(180, 270), scale=1)
    again = create_scene_artwork(create_brief_for_song(a), size=(180, 270), scale=1)
    other = create_scene_artwork(create_brief_for_song(b), size=(180, 270), scale=1)
    assert one.tobytes() == again.tobytes()
    assert one.tobytes() != other.tobytes()


@pytest.mark.parametrize("position", ["bottom", "top"])
@pytest.mark.parametrize("title,artist", [
    ("Blinding Lights", "The Weeknd"),
    ("The Extraordinarily Long Title of a Song That Never Ends and Keeps Going", "An Artist With A Very Long Name Feat. Many Others"),
    ("너의 이름을 부르면", "새벽 밴드"),
    ("", ""),
])
def test_overlay_handles_any_text(title, artist, position):
    brief = create_brief_for_song(CATALOG[0])
    art = create_scene_artwork(brief, size=(360, 540), scale=1)
    poster = add_title_overlay(art, title=title, artist=artist, style=brief.style,
                               palette=brief.palette, tagline="POP · 2019", position=position)
    out = BytesIO()
    poster.save(out, format="PNG")
    out.seek(0)
    with Image.open(out) as reopened:
        assert reopened.size == (360, 540)


def test_overlay_actually_draws_text_near_the_edge():
    brief = create_brief_for_song(CATALOG[0])
    art = create_scene_artwork(brief, size=(360, 540), scale=1)
    plain = add_title_overlay(art, title=" ", artist=" ", style=brief.style, palette=brief.palette)
    titled = add_title_overlay(art, title="WWWW", artist="MMMM", style=brief.style, palette=brief.palette)
    assert plain.tobytes() != titled.tobytes()
    assert titled.crop((0, 400, 360, 540)).convert("L").getextrema()[1] > 240  # near-white title pixels
