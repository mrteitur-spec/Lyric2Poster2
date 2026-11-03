from __future__ import annotations

from pathlib import Path
import sys
import streamlit as st

# Find the package whether the project files are at the repository root or one
# folder below it. This avoids ModuleNotFoundError when an extracted project
# folder is accidentally uploaded as a nested directory on GitHub.
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = None
_search_roots = [APP_DIR]
try:
    _search_roots.extend(
        item for item in APP_DIR.iterdir()
        if item.is_dir() and not item.name.startswith(".")
    )
except OSError:
    pass

for _candidate in _search_roots:
    if (_candidate / "songposter" / "__init__.py").is_file():
        PROJECT_ROOT = _candidate
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

if PROJECT_ROOT is None:
    st.set_page_config(page_title="Song Poster Studio", page_icon="🎧")
    st.title("🎧 Song Poster Studio")
    st.error("The application package folder is missing. Please upload the complete project files to GitHub.")
    st.markdown("The repository must contain `streamlit_app.py`, `requirements.txt`, and the `songposter/` folder.")
    st.code(
        "Lyric2Poster/\n"
        "├── streamlit_app.py\n"
        "├── requirements.txt\n"
        "├── songposter/\n"
        "│   ├── __init__.py\n"
        "│   ├── art_director.py\n"
        "│   └── ...\n"
        "└── data/"
    )
    st.stop()

ROOT = PROJECT_ROOT

try:
    from songposter.art_director import MOODS, create_brief_for_song, create_demo_brief
    from songposter.catalog import filter_songs, genres, load_catalog
    from songposter.limits import BRIEF_LIMIT, POSTER_LIMIT
    from songposter.models import ArtBrief
    from songposter.overlay import add_title_overlay
    from songposter.scene_engine import create_scene_artwork
    from songposter.styles import MATCH_SONG, STYLE_PRESETS
except ModuleNotFoundError as exc:
    st.set_page_config(page_title="Song Poster Studio", page_icon="🎧")
    st.title("🎧 Song Poster Studio")
    st.error(f"A required application module is missing: {exc.name}")
    st.info("Check that all files inside the songposter/ folder were uploaded to the repository.")
    st.stop()

import random
from io import BytesIO

st.set_page_config(
    page_title="Song Poster Studio",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

SOURCE_POPULAR, SOURCE_CUSTOM = "Popular songs", "My own song"
AUTO_MOOD = "Auto (from lyrics)"


@st.cache_data(show_spinner=False)
def get_catalog():
    return load_catalog()


@st.cache_data(show_spinner=False, max_entries=16)
def render_poster(brief: dict, title: str, artist: str, tagline: str, position: str) -> bytes:
    """Draw artwork + typography. Cached, so toggling title position is instant."""
    art = ArtBrief.from_dict(brief)
    background = create_scene_artwork(art, size=(900, 1350))
    poster = add_title_overlay(
        background, title=title, artist=artist, style=art.style,
        palette=art.palette, tagline=tagline, position=position.lower(),
    )
    buffer = BytesIO()
    poster.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


CATALOG = get_catalog()
BY_LABEL = {song.label: song for song in CATALOG}


def initialize_state() -> None:
    defaults = {
        "brief_count": 0, "poster_count": 0, "art_brief": None, "poster_meta": None,
        "app_error": None, "source": SOURCE_POPULAR, "genre_filter": "All", "song_query": "",
        "song_choice": None, "poster_look": MATCH_SONG, "title_position": "Bottom",
        "custom_title": "", "custom_artist": "", "custom_mood": AUTO_MOOD,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_poster() -> None:
    st.session_state["art_brief"] = None
    st.session_state["poster_meta"] = None
    st.session_state["app_error"] = None


def surprise_me() -> None:
    pool = filter_songs(CATALOG, st.session_state.get("genre_filter", "All"), st.session_state.get("song_query", ""))
    if pool:
        st.session_state["song_choice"] = random.choice(pool).label
        clear_poster()


def request_poster() -> None:
    """Build the lyric-free brief (consuming any lyrics), then store it for rendering."""
    ss = st.session_state
    look = ss.get("poster_look", MATCH_SONG)
    try:
        if ss.get("poster_count", 0) >= POSTER_LIMIT or ss.get("brief_count", 0) >= BRIEF_LIMIT:
            ss["app_error"] = f"Session limit reached ({POSTER_LIMIT} posters). Refresh the page to start a new session."
            return
        if ss.get("source") == SOURCE_POPULAR:
            song = BY_LABEL.get(ss.get("song_choice") or "")
            if song is None:
                ss["app_error"] = "Please choose a song first."
                return
            brief = create_brief_for_song(song, style=look)
            meta = {"title": song.title, "artist": song.artist, "tagline": song.tagline}
        else:
            title, artist = ss.get("custom_title", "").strip(), ss.get("custom_artist", "").strip()
            mood = ss.get("custom_mood", AUTO_MOOD)
            lyrics = ss.get("lyrics_input", "")
            if not title or not artist:
                ss["app_error"] = "Please enter both a song title and an artist."
                return
            if not lyrics.strip() and mood == AUTO_MOOD:
                ss["app_error"] = "Paste a short lyric excerpt you may use, or pick a mood."
                return
            brief = create_demo_brief(title=title, artist=artist, lyrics=lyrics, style=look,
                                      mood=None if mood == AUTO_MOOD else mood)
            meta = {"title": title, "artist": artist, "tagline": ""}
        meta["variation"] = 0
        meta["base_seed"] = brief.seed
        ss["art_brief"], ss["poster_meta"] = brief.to_dict(), meta
        ss["brief_count"] = ss.get("brief_count", 0) + 1
        ss["poster_count"] = ss.get("poster_count", 0) + 1
        ss["app_error"] = None
    except Exception as exc:  # Do not include user input in error text.
        ss["app_error"] = f"Could not create the poster ({type(exc).__name__})."
    finally:
        ss.pop("lyrics_input", None)  # lyrics never outlive this callback


def new_variation() -> None:
    ss = st.session_state
    if not ss.get("art_brief") or ss.get("poster_count", 0) >= POSTER_LIMIT:
        return
    meta = dict(ss["poster_meta"])
    meta["variation"] = meta.get("variation", 0) + 1
    brief = dict(ss["art_brief"])
    brief["seed"] = f"{meta['base_seed']}#{meta['variation']}"
    ss["art_brief"], ss["poster_meta"] = brief, meta
    ss["poster_count"] = ss.get("poster_count", 0) + 1


def swatches(colors) -> None:
    cols = st.columns(len(colors))
    for col, color in zip(cols, colors):
        col.markdown(
            f"<div style='height:30px;border-radius:8px;background:{color};border:1px solid #777'></div>"
            f"<div style='text-align:center;font-size:0.72rem;opacity:.8'>{color}</div>",
            unsafe_allow_html=True,
        )


initialize_state()

st.title("🎧 Song Poster Studio")
st.caption("Pick a hit, get a poster that looks and feels like the song. Drawn locally, no API keys needed.")

with st.sidebar:
    st.header("Studio settings")
    st.selectbox(
        "Poster look", [MATCH_SONG, *STYLE_PRESETS], key="poster_look",
        help="“Match the song” uses each song's own colours and style. Applies to the next poster you create.",
    )
    st.radio("Title position", ["Bottom", "Top"], key="title_position", horizontal=True)
    st.divider()
    st.markdown("**Session usage**")
    st.metric("Posters", f"{st.session_state['poster_count']} / {POSTER_LIMIT}")
    st.caption("Counters are held in this Streamlit session and reset with a new session.")

left, right = st.columns([1.0, 1.0], gap="large")

with left:
    st.subheader("1. Choose a song")
    st.radio("Source", [SOURCE_POPULAR, SOURCE_CUSTOM], key="source", horizontal=True,
             label_visibility="collapsed", on_change=clear_poster)

    if st.session_state["source"] == SOURCE_POPULAR:
        g_col, q_col = st.columns([0.4, 0.6])
        g_col.selectbox("Genre", ["All", *genres(CATALOG)], key="genre_filter")
        q_col.text_input("Search", key="song_query", placeholder="Title or artist…")
        pool = filter_songs(CATALOG, st.session_state["genre_filter"], st.session_state["song_query"])
        labels = [song.label for song in pool]
        if st.session_state.get("song_choice") not in labels:
            st.session_state["song_choice"] = None
        st.selectbox(
            f"Popular songs ({len(labels)})", labels, index=None, key="song_choice",
            placeholder="Choose a song…", on_change=clear_poster,
        )
        st.button("🎲 Surprise me", on_click=surprise_me, disabled=not labels)

        song = BY_LABEL.get(st.session_state.get("song_choice") or "")
        if song:
            with st.container(border=True):
                st.markdown(f"### {song.title}")
                st.markdown(f"**{song.artist}** · {song.genre}" + (f" · {song.year}" if song.year else ""))
                st.write(f"*{song.mood.title()}* · {song.themes}")
                st.caption("Scene: " + " + ".join(song.motifs))
                swatches(song.palette)
            if song.public_domain:
                st.caption("Public-domain lyrics are built in for this song.")
            else:
                st.caption("No lyrics needed: this song's mood, themes and colours are already built in.")
        st.button(
            "Create poster", type="primary", width="stretch", on_click=request_poster,
            disabled=song is None or st.session_state["poster_count"] >= POSTER_LIMIT,
        )
    else:
        st.info("Lyrics are used only in memory to choose the mood and scene, then discarded. "
                "Only paste text you are allowed to use.")
        with st.form("custom_form", clear_on_submit=False):
            st.text_input("Song title", key="custom_title", placeholder="Enter the song title")
            st.text_input("Artist", key="custom_artist", placeholder="Enter the artist name")
            st.selectbox("Mood", [AUTO_MOOD, *MOODS], key="custom_mood")
            st.text_area("Lyrics (optional if you pick a mood)", key="lyrics_input", height=150,
                         placeholder="Paste a short excerpt you are permitted to use…")
            st.form_submit_button(
                "Create poster", type="primary", width="stretch", on_click=request_poster,
                disabled=st.session_state["poster_count"] >= POSTER_LIMIT,
            )

    if st.session_state.get("app_error"):
        st.error(st.session_state["app_error"])

with right:
    st.subheader("2. Your poster")
    raw_brief, meta = st.session_state.get("art_brief"), st.session_state.get("poster_meta")
    if raw_brief and meta:
        try:
            with st.spinner("Painting your poster…"):
                png = render_poster(raw_brief, meta["title"], meta["artist"], meta["tagline"],
                                    st.session_state["title_position"])
            st.image(png, width="stretch")
            safe = "_".join(meta["title"].split()) or "poster"
            safe = "".join(ch for ch in safe if ch.isalnum() or ch in "_-") or "poster"
            d_col, v_col = st.columns(2)
            d_col.download_button("Download PNG", data=png, file_name=f"{safe[:48]}_poster.png",
                                  mime="image/png", type="primary", width="stretch")
            v_col.button("🔄 New variation", on_click=new_variation, width="stretch",
                         disabled=st.session_state["poster_count"] >= POSTER_LIMIT,
                         help="Same song and colours, a different arrangement.")
            with st.expander("Art direction"):
                brief = ArtBrief.from_dict(raw_brief)
                st.markdown(f"**{brief.concept}**")
                st.write(brief.description)
                st.caption("Scene: " + " + ".join(brief.scene_motifs) + f" · Style: {brief.style}")
                swatches(brief.palette)
        except Exception as exc:
            st.error(f"Could not generate the poster ({type(exc).__name__}).")
    else:
        st.markdown(
            "<div style='aspect-ratio:2/3;max-width:420px;border:1px dashed #777;border-radius:14px;"
            "display:flex;align-items:center;justify-content:center;color:#888;text-align:center;padding:1rem'>"
            "Pick a song and press <b>&nbsp;Create poster&nbsp;</b></div>",
            unsafe_allow_html=True,
        )

st.divider()
with st.expander("About this app"):
    st.markdown(
        """
        - Song moods, themes and colours are descriptive notes written for this app. Copyrighted lyrics are not included.
        - Artwork is generated locally with Pillow; the title and artist are real text drawn on top.
        - Custom lyrics are read once to choose a mood and scene, then removed from session state.
        - Poster counters are per browser session.
        """
    )
st.caption("Song Poster Studio · independent demo implementation")
