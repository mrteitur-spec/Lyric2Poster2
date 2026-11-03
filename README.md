# Song Poster Studio

Pick a popular song and get a poster that looks and feels like it: song-specific artwork,
the song's own colours, and a big, obvious title and artist. Everything is drawn locally with
Pillow, so no API keys are needed.

## What's new in v2

- **Popular-song picker**: 41 songs across Pop, Rock, K-Pop, Hip-Hop/R&B and Traditional.
  Filter by genre, search by title or artist, or press *Surprise me*. Choosing a song fills in the
  title, artist, mood, themes and colours automatically; no typing and no lyrics needed.
- **Artwork that matches the song**: 19 scene motifs (neon skyline, retro sun, rain, flowers,
  flames, road, vinyl, spotlight, fireworks, ...). Each song has a hero motif plus a supporting one,
  its own palette, and its own seed, so every poster is different but repeatable.
- **Bold typography**: large title that auto-fits up to 3 lines, wide-tracked artist name with an
  accent bar, small genre/year tagline, soft shadow and a dark gradient for legibility. Fonts are
  bundled (Anton, Bebas Neue, DM Serif Display, Poppins; SIL Open Font License) and chosen by style.
  Korean/CJK titles work. Title can sit at the **bottom or top**.
- **New variation** button, one-click **Create poster**, PNG download.
- "My own song" mode still works: paste lyrics (used once, then discarded) or just pick a mood.

## Lyrics and copyright

The catalog holds *descriptive* notes written for this app (mood, themes, colours), not lyrics of
copyrighted songs. Only public-domain songs (e.g. *Amazing Grace*) carry their lyrics. To make a
poster for any song you have a right to use, use **My own song** and paste your own excerpt.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Run tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Add or edit songs

Open `data/catalog/popular_songs.json` and add an entry:

```json
{
  "id": "my-song", "title": "My Song", "artist": "My Artist", "year": 2024, "genre": "Pop",
  "mood": "hopeful", "style": "Retro",
  "motifs": ["sun", "clouds"],
  "palette": ["#2B1236", "#C8503C", "#F4A94E", "#FBE3B0"],
  "themes": "a short description in your own words"
}
```

- `motifs`: first = hero, second = supporting. Choose from: sun, moon, stars, skyline, waves, rain,
  mountains, flowers, flames, road, vinyl, grid, ribbons, heart, spotlight, lightning, bubbles,
  clouds, fireworks.
- `palette`: four `#RRGGBB` colours (the engine sorts them dark to light).
- `style`: Aurora, Minimal, Retro, Noir, Dreamscape or Geometric (controls the font pairing).
- Invalid entries are skipped, never fatal.

## Deploy on Streamlit Community Cloud

1. Push the **contents** of this folder to the root of your GitHub repository.
2. Confirm `streamlit_app.py`, `requirements.txt`, `packages.txt`, `assets/`, `data/` and `songposter/`
   sit together at the repository root.
3. Deploy (main file: `streamlit_app.py`) or reboot the existing app. No secrets are required.
4. `packages.txt` installs a Korean font (`fonts-nanum`) so Hangul titles render correctly.

If you ever see `ModuleNotFoundError: No module named 'songposter'`, see `DEPLOYMENT_FIX.md`.

## Project structure

```text
streamlit_app.py            app UI
packages.txt                system fonts for Korean/CJK titles
assets/fonts/               bundled open-licence fonts
data/catalog/popular_songs.json   song catalog (edit me)
songposter/
  catalog.py                load/filter the catalog
  art_director.py           moods, scene picking, art briefs
  scene_engine.py           song-specific artwork (19 motifs)
  overlay.py                title/artist typography
  styles.py, models.py, safety.py, limits.py, charts.py, image_engine.py
tests/                      42 tests
```
