from __future__ import annotations

import csv
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import grid_graffiti as grid


class TextRenderingTests(unittest.TestCase):
    def test_normalise_text_uppercases_supported_text(self) -> None:
        self.assertEqual(grid.normalise_text("hello 42!?-."), "HELLO 42!?-.")

    def test_normalise_text_rejects_empty_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty"):
            grid.normalise_text("")

    def test_normalise_text_rejects_unsupported_characters(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            grid.normalise_text("hello@")

    def test_text_bitmap_for_hello_has_expected_shape(self) -> None:
        bitmap = grid.text_bitmap("HELLO")

        self.assertEqual(len(bitmap), grid.ROWS)
        self.assertEqual(len(bitmap[0]), 29)
        self.assertTrue(all(len(row) == 29 for row in bitmap))
        self.assertEqual(sum(sum(row) for row in bitmap), 73)

    def test_ascii_preview_pads_to_full_grid_width(self) -> None:
        bitmap = grid.text_bitmap("HI")
        preview = grid.ascii_preview(bitmap, "center")

        lines = preview.splitlines()
        self.assertEqual(len(lines), grid.ROWS)
        self.assertTrue(all(len(line) == grid.COLUMNS for line in lines))


class CalendarMappingTests(unittest.TestCase):
    def test_current_week_sunday(self) -> None:
        self.assertEqual(
            grid.current_week_sunday(date(2026, 6, 20)),
            date(2026, 6, 14),
        )
        self.assertEqual(
            grid.current_week_sunday(date(2026, 6, 21)),
            date(2026, 6, 21),
        )

    def test_grid_start_is_52_weeks_before_current_week(self) -> None:
        self.assertEqual(grid.grid_start(date(2026, 6, 20)), date(2025, 6, 15))

    def test_lit_pixels_map_columns_rows_to_dates(self) -> None:
        bitmap = grid.text_bitmap("HELLO")
        pixels = grid.lit_pixels(bitmap, date(2026, 6, 20), "left")

        self.assertEqual(len(pixels), 73)
        self.assertIn(grid.Pixel(column=0, row=0, day=date(2025, 6, 15)), pixels)
        self.assertIn(grid.Pixel(column=28, row=5, day=date(2026, 1, 2)), pixels)

    def test_alignment_offsets(self) -> None:
        self.assertEqual(grid.placement_offset(10, "left"), 0)
        self.assertEqual(grid.placement_offset(10, "center"), 21)
        self.assertEqual(grid.placement_offset(10, "right"), 43)

    def test_oversized_text_is_rejected(self) -> None:
        bitmap = grid.text_bitmap("HELLOHELLO")

        with self.assertRaisesRegex(ValueError, "grid is only"):
            grid.lit_pixels(bitmap, date(2026, 6, 20), "left")


class ExportTests(unittest.TestCase):
    def test_write_csv_exports_expected_rows(self) -> None:
        pixels = [
            grid.Pixel(column=0, row=0, day=date(2026, 1, 4)),
            grid.Pixel(column=1, row=6, day=date(2026, 1, 17)),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "grid-dates.csv"
            grid.write_csv(path, pixels, commits_per_pixel=3)

            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(rows[0]["weekday"], "Sun")
        self.assertEqual(rows[0]["date"], "2026-01-04")
        self.assertEqual(rows[0]["commits_for_cell"], "3")
        self.assertEqual(rows[1]["weekday"], "Sat")

    def test_write_svg_escapes_title_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "grid-preview.svg"
            grid.write_svg(
                path,
                'HELLO "DEMO"',
                date(2026, 6, 20),
                [grid.Pixel(column=0, row=0, day=date(2025, 6, 15))],
            )
            svg = path.read_text(encoding="utf-8")

        self.assertIn("&quot;DEMO&quot;", svg)
        self.assertIn('fill="#39d353"', svg)


class SafetyAndCliTests(unittest.TestCase):
    def test_resolve_contributor_uses_explicit_values(self) -> None:
        contributor = grid.resolve_contributor(
            "Ada Lovelace",
            "ada@example.com",
            ROOT,
        )

        self.assertEqual(contributor.name, "Ada Lovelace")
        self.assertEqual(contributor.email, "ada@example.com")

    def test_resolve_contributor_rejects_invalid_email(self) -> None:
        with self.assertRaisesRegex(ValueError, "email"):
            grid.resolve_contributor("Ada Lovelace", "not-an-email", ROOT)

    def test_ensure_safe_output_dir_rejects_non_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "existing.txt").write_text("data", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "not empty"):
                grid.ensure_safe_output_dir(output_dir, write_repo=True)

    def test_ensure_safe_output_dir_rejects_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "file"
            output_path.write_text("data", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "not a directory"):
                grid.ensure_safe_output_dir(output_path, write_repo=True)

    def test_main_dry_run_returns_success(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = grid.main(["HELLO", "--today", "2026-06-20"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Dry run only", stdout.getvalue())

    def test_main_returns_error_for_invalid_text(self) -> None:
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            exit_code = grid.main(["HELLO@"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Unsupported", stderr.getvalue())


@unittest.skipIf(shutil.which("git") is None, "git is required")
class GitGenerationTests(unittest.TestCase):
    def test_create_local_repo_writes_dated_commits_without_remote(self) -> None:
        pixels = [
            grid.Pixel(column=0, row=0, day=date(2026, 1, 4)),
            grid.Pixel(column=0, row=1, day=date(2026, 1, 5)),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo"
            commit_count = grid.create_local_repo(
                repo,
                pixels,
                commits_per_pixel=2,
                commit_hour=9,
                contributor=grid.Contributor(
                    name="Test Contributor",
                    email="test@example.com",
                ),
            )

            rev_count = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=repo,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()
            dates = subprocess.run(
                ["git", "log", "--reverse", "--pretty=%ad", "--date=short"],
                cwd=repo,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.splitlines()
            remotes = subprocess.run(
                ["git", "remote"],
                cwd=repo,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()
            author = subprocess.run(
                ["git", "log", "-1", "--format=%an <%ae>"],
                cwd=repo,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()

            self.assertEqual(commit_count, 4)
            self.assertEqual(rev_count, "4")
            self.assertEqual(
                dates,
                ["2026-01-04", "2026-01-04", "2026-01-05", "2026-01-05"],
            )
            self.assertEqual(remotes, "")
            self.assertEqual(author, "Test Contributor <test@example.com>")
            self.assertEqual(
                (repo / "pixels.txt").read_text(encoding="utf-8").splitlines(),
                [
                    "0001,column=0,row=0,day=2026-01-04,layer=1",
                    "0002,column=0,row=0,day=2026-01-04,layer=2",
                    "0003,column=0,row=1,day=2026-01-05,layer=1",
                    "0004,column=0,row=1,day=2026-01-05,layer=2",
                ],
            )


if __name__ == "__main__":
    unittest.main()
