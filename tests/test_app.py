import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from streamlit.testing.v1 import AppTest

import image_search


APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")


def make_result(run_dir: Path, image_count: int) -> image_search.SearchResult:
    image_dir = run_dir / "bing"
    image_dir.mkdir(parents=True)
    images = []
    for index in range(image_count):
        image_path = image_dir / f"{index:03}.png"
        Image.new("RGB", (2, 2), color="purple").save(image_path)
        images.append(image_path)

    return image_search.SearchResult(
        run_dir=run_dir,
        images=tuple(images),
        successful_engines=("Bing",),
        failed_engines=(),
    )


class AppTests(unittest.TestCase):
    def test_initial_widgets_and_maximum_limits(self):
        app = AppTest.from_file(APP_PATH).run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.text_input[0].value, "Dog")
        self.assertEqual(app.multiselect[0].value, ["Bing"])
        self.assertEqual(app.number_input[0].value, 100)
        self.assertEqual(app.number_input[0].min, 1)
        self.assertEqual(app.number_input[0].max, 500)

    def test_blank_keyword_does_not_start_search(self):
        app = AppTest.from_file(APP_PATH).run()
        app.text_input[0].set_value("   ")
        app.button[0].click()

        with patch("image_search.run_search") as run_search:
            app.run()

        run_search.assert_not_called()
        self.assertEqual([error.value for error in app.error], [
            "Please enter a search word."
        ])
        self.assertEqual(len(app.exception), 0)

    def test_empty_engine_selection_does_not_start_search(self):
        app = AppTest.from_file(APP_PATH).run()
        app.multiselect[0].set_value([])
        app.button[0].click()

        with patch("image_search.run_search") as run_search:
            app.run()

        run_search.assert_not_called()
        self.assertEqual([error.value for error in app.error], [
            "Please select at least one search engine."
        ])
        self.assertEqual(len(app.exception), 0)

    def test_zero_one_four_and_five_images_render_without_error(self):
        for image_count in (0, 1, 4, 5):
            with self.subTest(image_count=image_count):
                with tempfile.TemporaryDirectory() as temp_dir:
                    result = make_result(Path(temp_dir) / "run-test", image_count)
                    app = AppTest.from_file(APP_PATH).run()
                    app.button[0].click()

                    with patch("image_search.run_search", return_value=result):
                        app.run()

                    self.assertEqual(len(app.exception), 0)
                    self.assertEqual(len(app.get("image")), image_count)
                    if image_count:
                        self.assertEqual(
                            [success.value for success in app.success],
                            ["Completion."],
                        )
                    else:
                        self.assertEqual(
                            [warning.value for warning in app.warning],
                            ["No images were found."],
                        )

    def test_partial_failure_is_reported_without_exception_details(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = make_result(Path(temp_dir) / "run-test", 1)
            result = image_search.SearchResult(
                run_dir=result.run_dir,
                images=result.images,
                successful_engines=("Bing",),
                failed_engines=("Google",),
            )
            app = AppTest.from_file(APP_PATH).run()
            app.button[0].click()

            with patch("image_search.run_search", return_value=result):
                app.run()

            self.assertEqual(
                [error.value for error in app.error],
                ["Failed to get images from Google."],
            )
            self.assertEqual(
                [warning.value for warning in app.warning],
                ["Search completed with some errors."],
            )
            self.assertNotIn("crawler details", str(app))
            self.assertEqual(len(app.exception), 0)

    def test_unexpected_startup_failure_is_logged_but_not_exposed(self):
        app = AppTest.from_file(APP_PATH).run()
        app.button[0].click()

        with self.assertLogs("image_search_app", level="ERROR") as logs:
            with patch(
                "image_search.run_search",
                side_effect=OSError("private filesystem details"),
            ):
                app.run()

        self.assertIn("private filesystem details", "\n".join(logs.output))
        self.assertEqual(
            [error.value for error in app.error],
            ["Image search could not be started."],
        )
        self.assertNotIn("private filesystem details", str(app))
        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
