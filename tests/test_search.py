import tempfile
import unittest
from pathlib import Path

from image_search_app import search


def crawler_that_creates(filename: str = "result.jpg"):
    class CreatingCrawler:
        def __init__(self, downloader_threads, storage):
            self.root_dir = Path(storage["root_dir"])

        def crawl(self, keyword, max_num, filters=None):
            (self.root_dir / filename).write_bytes(b"image")

    return CreatingCrawler


class FailingCrawler:
    def __init__(self, downloader_threads, storage):
        pass

    def crawl(self, keyword, max_num, filters=None):
        raise RuntimeError("crawler details must stay in the server log")


class EmptyCrawler:
    def __init__(self, downloader_threads, storage):
        pass

    def crawl(self, keyword, max_num, filters=None):
        pass


class ImageSearchTests(unittest.TestCase):
    def test_untrusted_keywords_never_become_part_of_the_run_path(self):
        keywords = ("../outside", "C:\\absolute\\path", '<>:"/\\|?*')

        with tempfile.TemporaryDirectory() as temp_dir:
            download_dir = Path(temp_dir) / "images"
            resolved_base = download_dir.resolve()

            for keyword in keywords:
                with self.subTest(keyword=keyword):
                    result = search.run_search(
                        keywords=keyword,
                        engines=["Bing"],
                        max_num=1,
                        download_dir=download_dir,
                        crawler_types={"Bing": crawler_that_creates()},
                    )

                    self.assertTrue(result.run_dir.is_relative_to(resolved_base))
                    self.assertEqual(result.run_dir.parent, resolved_base)
                    self.assertTrue(result.run_dir.name.startswith("run-"))
                    self.assertNotIn(keyword, result.run_dir.name)

    def test_all_engines_succeed_and_use_separate_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = search.run_search(
                keywords="grape",
                engines=["Bing", "Google"],
                max_num=10,
                download_dir=Path(temp_dir) / "images",
                crawler_types={
                    "Bing": crawler_that_creates("bing.jpg"),
                    "Google": crawler_that_creates("google.png"),
                },
            )

            self.assertEqual(result.successful_engines, ("Bing", "Google"))
            self.assertEqual(result.failed_engines, ())
            self.assertEqual(
                [path.relative_to(result.run_dir).as_posix() for path in result.images],
                [
                    "bing/keyword-01/bing.jpg",
                    "google/keyword-01/google.png",
                ],
            )

    def test_partial_success_returns_images_and_failed_engine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertLogs(search.LOGGER, level="ERROR"):
                result = search.run_search(
                    keywords="grape",
                    engines=["Bing", "Google"],
                    max_num=10,
                    download_dir=Path(temp_dir) / "images",
                    crawler_types={
                        "Bing": crawler_that_creates(),
                        "Google": FailingCrawler,
                    },
                )

            self.assertEqual(result.successful_engines, ("Bing",))
            self.assertEqual(result.failed_engines, ("Google",))
            self.assertEqual(
                result.failed_searches,
                (search.SearchFailure(engine="Google", keyword="grape"),),
            )
            self.assertEqual(len(result.images), 1)

    def test_all_failures_return_no_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertLogs(search.LOGGER, level="ERROR"):
                result = search.run_search(
                    keywords="grape",
                    engines=["Bing", "Google"],
                    max_num=10,
                    download_dir=Path(temp_dir) / "images",
                    crawler_types={
                        "Bing": FailingCrawler,
                        "Google": FailingCrawler,
                    },
                )

            self.assertEqual(result.successful_engines, ())
            self.assertEqual(result.failed_engines, ("Bing", "Google"))
            self.assertEqual(result.images, ())

    def test_successful_crawler_can_return_zero_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = search.run_search(
                keywords="no results",
                engines=["Bing"],
                max_num=10,
                download_dir=Path(temp_dir) / "images",
                crawler_types={"Bing": EmptyCrawler},
            )

            self.assertEqual(result.successful_engines, ("Bing",))
            self.assertEqual(result.failed_engines, ())
            self.assertEqual(result.images, ())

    def test_invalid_inputs_do_not_create_download_directory(self):
        invalid_cases = (
            {"keywords": " ", "engines": ["Bing"], "max_num": 1},
            {"keywords": "grape", "engines": [], "max_num": 1},
            {"keywords": "grape", "engines": ["Bing"], "max_num": 0},
            {"keywords": "grape", "engines": ["Bing"], "max_num": 501},
            {
                "keywords": [f"word-{index}" for index in range(11)],
                "engines": ["Bing"],
                "max_num": 1,
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            download_dir = Path(temp_dir) / "images"
            for case in invalid_cases:
                with self.subTest(case=case):
                    with self.assertRaises(ValueError):
                        search.run_search(
                            **case,
                            download_dir=download_dir,
                            crawler_types={"Bing": EmptyCrawler},
                        )
                    self.assertFalse(download_dir.exists())

    def test_google_is_not_available_in_the_production_crawler_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            download_dir = Path(temp_dir) / "images"

            with self.assertRaisesRegex(ValueError, "Unsupported search engine"):
                search.run_search(
                    keywords="grape",
                    engines=["Google"],
                    max_num=1,
                    download_dir=download_dir,
                )

            self.assertFalse(download_dir.exists())

    def test_multiple_keywords_are_deduplicated_and_use_separate_directories(self):
        calls = []

        class RecordingCrawler:
            def __init__(self, downloader_threads, storage):
                self.root_dir = Path(storage["root_dir"])

            def crawl(self, keyword, max_num, filters=None):
                calls.append((keyword, max_num, filters))
                (self.root_dir / "result.jpg").write_bytes(b"image")

        with tempfile.TemporaryDirectory() as temp_dir:
            result = search.run_search(
                keywords=[" Red grape ", "green grape", "red GRAPE", ""],
                engines=["Bing"],
                max_num=25,
                download_dir=Path(temp_dir) / "images",
                filters={"type": "photo", "layout": "wide", "size": ">640x480"},
                crawler_types={"Bing": RecordingCrawler},
            )

            self.assertEqual(
                calls,
                [
                    (
                        "Red grape",
                        25,
                        {"type": "photo", "layout": "wide", "size": ">640x480"},
                    ),
                    (
                        "green grape",
                        25,
                        {"type": "photo", "layout": "wide", "size": ">640x480"},
                    ),
                ],
            )
            self.assertEqual(
                [path.relative_to(result.run_dir).as_posix() for path in result.images],
                [
                    "bing/keyword-01/result.jpg",
                    "bing/keyword-02/result.jpg",
                ],
            )
            self.assertEqual(result.keywords, ("Red grape", "green grape"))

    def test_invalid_filters_do_not_create_download_directory(self):
        invalid_filters = (
            {"unknown": "value"},
            {"type": "portrait"},
            {"size": ">0x480"},
            {"size": "640x480"},
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            download_dir = Path(temp_dir) / "images"
            for filters in invalid_filters:
                with self.subTest(filters=filters):
                    with self.assertRaises(ValueError):
                        search.run_search(
                            keywords="grape",
                            engines=["Bing"],
                            max_num=1,
                            download_dir=download_dir,
                            filters=filters,
                            crawler_types={"Bing": EmptyCrawler},
                        )
                    self.assertFalse(download_dir.exists())

    def test_collect_images_filters_and_sorts_supported_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "google").mkdir()
            (run_dir / "bing").mkdir()
            (run_dir / "google" / "B.PNG").write_bytes(b"image")
            (run_dir / "bing" / "a.jpg").write_bytes(b"image")
            (run_dir / "bing" / "notes.txt").write_text("not an image")

            images = search.collect_images(run_dir)

            self.assertEqual(
                [path.relative_to(run_dir).as_posix() for path in images],
                ["bing/a.jpg", "google/B.PNG"],
            )


if __name__ == "__main__":
    unittest.main()
