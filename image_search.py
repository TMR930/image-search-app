"""Image crawling and local storage helpers."""

from __future__ import annotations

import logging
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


@dataclass(frozen=True)
class SearchResult:
    """The outcome of one search run."""

    run_dir: Path
    images: tuple[Path, ...]
    successful_engines: tuple[str, ...]
    failed_engines: tuple[str, ...]


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
    keyword: str,
    engines: list[str],
    max_num: int,
    download_dir: Path,
    crawler_types: Mapping[str, type] | None = None,
) -> SearchResult:
    """Run the requested crawlers and return their combined local results."""
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("A search word is required.")
    if not engines:
        raise ValueError("At least one search engine is required.")
    if not 1 <= max_num <= 500:
        raise ValueError("The maximum number of images must be between 1 and 500.")

    available_crawlers = CRAWLER_TYPES if crawler_types is None else crawler_types
    unknown_engines = [engine for engine in engines if engine not in available_crawlers]
    if unknown_engines:
        raise ValueError(f"Unsupported search engine: {unknown_engines[0]}")

    run_dir = create_run_directory(download_dir)
    successful_engines: list[str] = []
    failed_engines: list[str] = []

    for engine in engines:
        engine_dir = run_dir / engine.lower()
        engine_dir.mkdir()
        try:
            crawler = available_crawlers[engine](
                downloader_threads=4,
                storage={"root_dir": str(engine_dir)},
            )
            crawler.crawl(keyword=keyword, max_num=max_num)
        except Exception:
            failed_engines.append(engine)
            LOGGER.exception("Image search failed for %s.", engine)
        else:
            successful_engines.append(engine)

    return SearchResult(
        run_dir=run_dir,
        images=collect_images(run_dir),
        successful_engines=tuple(successful_engines),
        failed_engines=tuple(failed_engines),
    )
