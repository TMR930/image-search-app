#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from pathlib import Path

import streamlit as st

import image_search

DOWNLOAD_DIR = Path("./images")
LOGGER = logging.getLogger("image_search_app")


def display_images(images: tuple[Path, ...], run_dir: Path) -> None:
    """Display images in rows of up to four columns."""
    for start in range(0, len(images), 4):
        columns = st.columns(4)
        for column, image_path in zip(columns, images[start : start + 4]):
            caption = image_path.relative_to(run_dir).as_posix()
            column.image(str(image_path), width=150, caption=caption)


st.title("Image Searcher")
search_text = st.text_input(label="Search word", value="Dog")
btn = st.button("search")

st.sidebar.title("Advanced Setting")
available_engines = list(image_search.CRAWLER_TYPES)
options = st.sidebar.multiselect(
    label="Search engine",
    options=available_engines,
    default=available_engines,
)
st.sidebar.caption("Google image search is temporarily unavailable.")
max_num = st.sidebar.number_input(
    label="Maximum number of images to acquire",
    min_value=1,
    max_value=500,
    value=100,
    step=1,
    help="Up to 500 images",
)

if btn:
    keyword = search_text.strip()
    if not keyword:
        st.error("Please enter a search word.")
    elif not options:
        st.error("Please select at least one search engine.")
    else:
        try:
            with st.spinner("Wait for it..."):
                result = image_search.run_search(
                    keyword=keyword,
                    engines=options,
                    max_num=max_num,
                    download_dir=DOWNLOAD_DIR,
                )
        except Exception:
            LOGGER.exception("Image search could not be started.")
            st.error("Image search could not be started.")
        else:
            for engine in result.failed_engines:
                st.error(f"Failed to get images from {engine}.")

            if result.images:
                st.write(f"files : {len(result.images)}")
                if result.failed_engines:
                    st.warning("Search completed with some errors.")
                else:
                    st.success("Completion.")
                display_images(result.images, result.run_dir)
            else:
                st.warning("No images were found.")
