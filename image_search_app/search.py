"""Image crawling and local storage helpers."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping
from uuid import uuid4

from icrawler.builtin import BingImageCrawler

LOGGER = logging.getLogger(__name__)

IMAGE_EXTENSIONS = frozenset(
    {".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
)
CRAWLER_TYPES = {
    "Bing": BingImageCrawler,
}
MAX_SEARCH_WORDS = 10
BING_FILTER_OPTIONS = {
    "type": ("photo", "clipart", "linedrawing", "transparent", "animated"),
    "color": (
        "color",
        "blackandwhite",
        "red",
        "orange",
        "yellow",
        "green",
        "teal",
        "blue",
        "purple",
        "pink",
        "white",
        "gray",
        "black",
        "brown",
    ),
    "size": ("small", "medium", "large", "extralarge"),
    "license": (
        "creativecommons",
        "publicdomain",
        "noncommercial",
        "commercial",
        "noncommercial,modify",
        "commercial,modify",
    ),
    "layout": ("square", "wide", "tall"),
    "people": ("face", "portrait"),
    "date": ("pastday", "pastweek", "pastmonth", "pastyear"),
}


@dataclass(frozen=True)
class SearchResult:
    """The outcome of one search run."""

    run_dir: Path
    images: tuple[Path, ...]
    successful_engines: tuple[str, ...]
    failed_engines: tuple[str, ...]
    failed_searches: tuple["SearchFailure", ...] = ()
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchFailure:
    """A failed engine and keyword combination."""

    engine: str
    keyword: str


def normalize_keywords(keywords: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Normalize, deduplicate, and validate search words."""
    candidates = keywords.splitlines() if isinstance(keywords, str) else keywords
    normalized: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        keyword = candidate.strip()
        key = keyword.casefold()
        if keyword and key not in seen:
            normalized.append(keyword)
            seen.add(key)

    if not normalized:
        raise ValueError("At least one search word is required.")
    if len(normalized) > MAX_SEARCH_WORDS:
        raise ValueError(f"No more than {MAX_SEARCH_WORDS} search words are allowed.")

    return tuple(normalized)


def normalize_bing_filters(filters: Mapping[str, str] | None) -> dict[str, str]:
    """Validate Bing filters before icrawler starts its worker threads."""
    normalized = {
        name: value.strip()
        for name, value in (filters or {}).items()
        if value and value.strip()
    }

    unknown_filters = normalized.keys() - BING_FILTER_OPTIONS.keys()
    if unknown_filters:
        raise ValueError(f"Unsupported Bing filter: {sorted(unknown_filters)[0]}")

    for name, value in normalized.items():
        if name == "size" and re.fullmatch(r">\d+x\d+", value):
            width, height = (int(part) for part in value[1:].split("x"))
            if width > 0 and height > 0:
                continue
        if value not in BING_FILTER_OPTIONS[name]:
            raise ValueError(f"Unsupported value for Bing filter {name}: {value}")

    return normalized


def create_run_directory(download_dir: Path) -> Path:
    """Create a unique directory that is guaranteed to be below download_dir."""
    base_dir = download_dir.resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = (base_dir / f"run-{timestamp}-{uuid4().hex[:8]}").resolve()
    if not run_dir.is_relative_to(base_dir):
        raise ValueError("The run directory must be inside the download directory.")

    run_dir.mkdir()
    return run_dir


def collect_images(run_dir: Path) -> tuple[Path, ...]:
    """Return supported image files below run_dir in a stable order."""
    if not run_dir.is_dir():
        return ()

    return tuple(
        sorted(
            (
                path
                for path in run_dir.rglob("*")
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            ),
            key=lambda path: path.relative_to(run_dir).as_posix().casefold(),
        )
    )


def run_search(
    keywords: str | list[str] | tuple[str, ...],
    engines: list[str],
    max_num: int,
    download_dir: Path,
    filters: Mapping[str, str] | None = None,
    crawler_types: Mapping[str, type] | None = None,
) -> SearchResult:
    """Run the requested crawlers and return their combined local results."""
    normalized_keywords = normalize_keywords(keywords)
    normalized_engines = list(dict.fromkeys(engines))
    if not normalized_engines:
        raise ValueError("At least one search engine is required.")
    if not 1 <= max_num <= 500:
        raise ValueError("The maximum number of images must be between 1 and 500.")
    normalized_filters = normalize_bing_filters(filters)

    available_crawlers = CRAWLER_TYPES if crawler_types is None else crawler_types
    unknown_engines = [
        engine for engine in normalized_engines if engine not in available_crawlers
    ]
    if unknown_engines:
        raise ValueError(f"Unsupported search engine: {unknown_engines[0]}")

    run_dir = create_run_directory(download_dir)
    successful_engines: list[str] = []
    failed_engines: list[str] = []
    failed_searches: list[SearchFailure] = []

    for engine in normalized_engines:
        engine_dir = run_dir / engine.lower()
        engine_dir.mkdir()
        engine_succeeded = False
        engine_failed = False

        for index, keyword in enumerate(normalized_keywords, start=1):
            keyword_dir = engine_dir / f"keyword-{index:02}"
            keyword_dir.mkdir()
            try:
                crawler = available_crawlers[engine](
                    downloader_threads=4,
                    storage={"root_dir": str(keyword_dir)},
                )
                crawler.crawl(
                    keyword=keyword,
                    max_num=max_num,
                    filters=normalized_filters or None,
                )
            except Exception:
                engine_failed = True
                failed_searches.append(SearchFailure(engine=engine, keyword=keyword))
                LOGGER.exception(
                    "Image search failed for %s with keyword %r.",
                    engine,
                    keyword,
                )
            else:
                engine_succeeded = True

        if engine_succeeded:
            successful_engines.append(engine)
        if engine_failed:
            failed_engines.append(engine)

    return SearchResult(
        run_dir=run_dir,
        images=collect_images(run_dir),
        successful_engines=tuple(successful_engines),
        failed_engines=tuple(failed_engines),
        failed_searches=tuple(failed_searches),
        keywords=normalized_keywords,
    )
