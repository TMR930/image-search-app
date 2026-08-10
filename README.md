# image-search-app

Search and save images from Bing using Streamlit and icrawler.

<<<<<<< HEAD
<img src="./assets/screen.gif" />
=======
<img src="./src/screen.gif" />
>>>>>>> origin/main

## Requirements

- [uv](https://docs.astral.sh/uv/)

The required Python version is managed through `.python-version` and installed by
uv when necessary.

## Setup

```shell
git clone https://github.com/tomcat930/image-search-app.git
cd image-search-app
uv sync --locked
```

## Usage

Launch the app.

```shell
uv run streamlit run app.py
```

Open <http://localhost:8501> in a browser. Search results are saved in a unique
directory below `data/runs/` for each run.

Enter one search word or phrase per line to run up to 10 searches at once. The
maximum number of images can be set from 1 to 500 for each search word.
Results are stored in input order under folders such as `keyword-01` and
`keyword-02`; the app displays the corresponding search words after completion.

The following Bing filters can be combined from the sidebar:

- Image type
- Color
- Size, including a custom minimum width and height
- License
- Layout
- People
- Date

Google image search is temporarily unavailable because its current response
format is not compatible with icrawler.

## Tests

```shell
uv run python -m unittest discover -s tests -v
```

## Code quality

Run Ruff lint and formatting checks.

```shell
uv run ruff check .
uv run ruff format --check .
```
