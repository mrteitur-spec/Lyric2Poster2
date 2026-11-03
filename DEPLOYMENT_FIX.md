# Streamlit Community Cloud deployment fix

The reported error was:

```text
ModuleNotFoundError: No module named 'songposter'
```

`streamlit_app.py` imports modules from the `songposter` Python package. The
package must be included in the GitHub repository. Uploading only the ZIP file
or only `streamlit_app.py` is not enough.

## Required repository layout

The recommended layout is:

```text
Lyric2Poster/
├── streamlit_app.py
├── requirements.txt
├── songposter/
│   ├── __init__.py
│   ├── art_director.py
│   ├── charts.py
│   ├── image_engine.py
│   ├── limits.py
│   ├── models.py
│   ├── overlay.py
│   ├── safety.py
│   └── styles.py
├── data/
│   └── charts/
│       └── sample_chart.csv
└── tests/
    └── test_core.py
```

The application now searches the repository root and one immediate child
folder for `songposter/`, so it can also recover from a common nested-folder
upload mistake. The recommended layout above is still the simplest option.

## Replace the broken repository files

1. Download and extract this fixed ZIP on your computer.
2. Open the extracted folder. Select **all files and folders inside it**.
3. Upload those files and folders to the **root** of your GitHub repository.
   Do not upload only the ZIP archive.
4. Confirm that GitHub shows both `streamlit_app.py` and the `songposter` folder
   at the same level.
5. In Streamlit Community Cloud, set the app's main file to `streamlit_app.py`.
6. Reboot the app from Streamlit Community Cloud.

No API keys are needed for the included demo mode.
