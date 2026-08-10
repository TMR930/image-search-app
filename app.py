#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from pathlib import Path

import streamlit as st

from image_search_app import search

PROJECT_ROOT = Path(__file__).resolve().parent
DOWNLOAD_DIR = PROJECT_ROOT / "data" / "runs"
LOGGER = logging.getLogger("image_search_app")


def display_images(images: tuple[Path, ...], run_dir: Path) -> None:
    """Display images in rows of up to four columns."""
    for start in range(0, len(images), 4):
        columns = st.columns(4)
        for column, image_path in zip(columns, images[start : start + 4]):
            caption = image_path.relative_to(run_dir).as_posix()
            column.image(str(image_path), width=150, caption=caption)


st.title("Image Searcher")
search_text = st.text_area(
    label="Search words",
    value="Dog",
    help="Enter one search word or phrase per line (up to 10).",
)
btn = st.button("search")

st.sidebar.title("Advanced Setting")
available_engines = list(search.CRAWLER_TYPES)
options = st.sidebar.multiselect(
    label="Search engine",
    options=available_engines,
    default=available_engines,
)
st.sidebar.caption("Google image search is temporarily unavailable.")
max_num = st.sidebar.number_input(
    label="Maximum images per search word",
    min_value=1,
    max_value=500,
    value=100,
    step=1,
    help="Up to 500 images",
)

st.sidebar.subheader("Filters")
filter_values = {
    name: st.sidebar.selectbox(
        label=name.replace("_", " ").title(),
        options=("Any", *values),
    )
    for name, values in search.BING_FILTER_OPTIONS.items()
    if name != "size"
}
size_options = ("Any", *search.BING_FILTER_OPTIONS["size"], "Custom minimum")
size_filter = st.sidebar.selectbox(label="Size", options=size_options)
if size_filter == "Custom minimum":
    minimum_width = st.sidebar.number_input(
        label="Minimum width",
        min_value=1,
        max_value=10000,
        value=640,
        step=1,
    )
    minimum_height = st.sidebar.number_input(
        label="Minimum height",
        min_value=1,
        max_value=10000,
        value=480,
        step=1,
    )
    filter_values["size"] = f">{minimum_width}x{minimum_height}"
elif size_filter != "Any":
    filter_values["size"] = size_filter

filters = {name: value for name, value in filter_values.items() if value != "Any"}

if btn:
    keywords = None
    try:
        normalized_keywords = search.normalize_keywords(search_text)
    except ValueError as exc:
        st.error(str(exc))
    else:
        keywords = list(normalized_keywords)

    if keywords is None:
        pass
    elif not options:
        st.error("Please select at least one search engine.")
    else:
        try:
            with st.spinner("Wait for it..."):
                result = search.run_search(
                    keywords=keywords,
                    engines=options,
                    max_num=max_num,
                    download_dir=DOWNLOAD_DIR,
                    filters=filters,
                )
        except Exception:
            LOGGER.exception("Image search could not be started.")
            st.error("Image search could not be started.")
        else:
            if result.failed_searches:
                for failure in result.failed_searches:
                    st.error(
                        f"Failed to get images from {failure.engine} "
                        f'for "{failure.keyword}".'
                    )
            else:
                for engine in result.failed_engines:
                    st.error(f"Failed to get images from {engine}.")

            if result.images:
                st.write(f"files : {len(result.images)}")
                if result.keywords:
                    folder_labels = "; ".join(
                        f"keyword-{index:02} = {keyword}"
                        for index, keyword in enumerate(result.keywords, start=1)
                    )
                    st.caption(f"Search folders: {folder_labels}")
                if result.failed_engines:
                    st.warning("Search completed with some errors.")
                else:
                    st.success("Completion.")
                display_images(result.images, result.run_dir)
            else:
                st.warning("No images were found.")
