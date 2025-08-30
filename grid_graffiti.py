#!/usr/bin/env python3
"""
grid_graffiti.py

Educational Git experiment:
- Converts text into a 5x7 bitmap.
- Maps lit pixels onto a 53-week, Sunday-to-Saturday calendar grid.
- Can preview the dates without writing anything.
- Can create a brand-new LOCAL-ONLY Git repository with dated commits.
- Refuses to operate in a repository that has any Git remote configured.
- Also exports an SVG and CSV manifest for blog/demo use.

This script does not push, add remotes, or modify an existing non-empty folder.

Examples:
    python grid_graffiti.py "HELLO"
    python grid_graffiti.py "HELLO" --today 2026-06-18
    python grid_graffiti.py "HELLO" --write-repo --output-dir hello-grid
    python grid_graffiti.py "HELLO" --align center --write-repo

Calendar model:
- 53 columns (weeks)
- 7 rows (Sunday through Saturday)
- The rightmost column is the week containing --today
- The leftmost column begins 52 weeks earlier
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

ROWS = 7
COLUMNS = 53
CELL = 12
GAP = 3
PADDING = 16
DAY_NAMES = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
SUPPORTED_TEXT = "A-Z, 0-9, space, ! ? - ."

FONT: dict[str, tuple[str, ...]] = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", ".#.#.", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),

    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("#...#", "#...#", "#...#", "#####", "....#", "....#", "....#"),
    "5": ("#####", "#....", "#....", "####.", "....#", "....#", "####."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),

    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", "..##.", "..##."),
    " ": ("...", "...", "...", "...", "...", "...", "..."),
}


@dataclass(frozen=True)
class Pixel:
    column: int
    row: int
    day: date


@dataclass(frozen=True)
class Contributor:
    name: str
    email: str


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Grid Graffiti: create a local-only Git history shaped like text on a 53x7 contribution grid."
    )
    parser.add_argument("text", help=f"Text to render: {SUPPORTED_TEXT}")
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=datetime.now().astimezone().date(),
        help="Calendar reference date in YYYY-MM-DD format. Default: local today.",
    )
    parser.add_argument(
        "--align",
        choices=("left", "center", "right"),
        default="left",
        help="Horizontal text alignment within the 53-week grid.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("grid-graffiti"),
        help="Folder for the SVG, CSV, and optional local repository.",
    )
    parser.add_argument(
        "--write-repo",
        action="store_true",
        help="Actually create the local Git repository. Without this flag, preview only.",
    )
    parser.add_argument(
        "--commits-per-pixel",
        type=int,
        default=1,
        choices=range(1, 6),
        metavar="1-5",
        help="Number of local commits per lit cell. Default: 1.",
    )
    parser.add_argument(
        "--commit-hour",
        type=int,
        default=12,
        choices=range(0, 24),
        metavar="0-23",
        help="Hour used for commit timestamps. Default: 12.",
    )
    parser.add_argument(
        "--author-name",
        help=(
            "Git author name for generated commits. Default: current Git "
            "user.name, then 'Grid Graffiti'."
        ),
    )
    parser.add_argument(
        "--author-email",
        help=(
            "Git author email for generated commits. Default: current Git "
            "user.email, then grid-graffiti@example.invalid. Use your GitHub "
            "noreply email if you want GitHub contributor attribution."
        ),
    )
    return parser.parse_args(argv)


def normalise_text(value: str) -> str:
    text = value.upper()
    unsupported = sorted({char for char in text if char not in FONT})
    if unsupported:
        readable = ", ".join(repr(char) for char in unsupported)
        raise ValueError(f"Unsupported character(s): {readable}")
    if not text:
        raise ValueError("Text cannot be empty.")
    return text


def text_bitmap(text: str) -> list[list[bool]]:
    """Render supported text into a seven-row bitmap."""
    rows: list[list[bool]] = [[] for _ in range(ROWS)]

    for char_index, char in enumerate(text):
        glyph = FONT[char]
        if len(glyph) != ROWS:
            raise RuntimeError(f"Glyph {char!r} is not seven rows tall.")

        if char_index:
            for row in rows:
                row.append(False)

        for y, glyph_row in enumerate(glyph):
            rows[y].extend(pixel == "#" for pixel in glyph_row)

    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise RuntimeError("Bitmap rows have inconsistent widths.")
    return rows


def current_week_sunday(reference: date) -> date:
    # Python: Monday=0 ... Sunday=6
    days_since_sunday = (reference.weekday() + 1) % 7
    return reference - timedelta(days=days_since_sunday)


def grid_start(reference: date) -> date:
    return current_week_sunday(reference) - timedelta(weeks=COLUMNS - 1)


def placement_offset(bitmap_width: int, alignment: str) -> int:
    if bitmap_width > COLUMNS:
        raise ValueError(
            f"Rendered text is {bitmap_width} columns wide, but the grid is only {COLUMNS}."
        )

    free = COLUMNS - bitmap_width
    if alignment == "left":
        return 0
    if alignment == "right":
        return free
    return free // 2


def lit_pixels(
    bitmap: list[list[bool]], reference: date, alignment: str
) -> list[Pixel]:
    """Map lit bitmap cells to contribution-grid dates."""
    start = grid_start(reference)
    width = len(bitmap[0])
    offset = placement_offset(width, alignment)

    pixels: list[Pixel] = []
    for row in range(ROWS):
        for x in range(width):
            if bitmap[row][x]:
                column = offset + x
                pixel_day = start + timedelta(days=column * 7 + row)
                pixels.append(Pixel(column=column, row=row, day=pixel_day))
    return pixels


def ascii_preview(bitmap: list[list[bool]], alignment: str) -> str:
    width = len(bitmap[0])
    offset = placement_offset(width, alignment)
    lines = []
    for row in bitmap:
        line = "." * offset
        line += "".join("#" if cell else "." for cell in row)
        line += "." * (COLUMNS - len(line))
        lines.append(line)
    return "\n".join(lines)


def ensure_safe_output_dir(output_dir: Path, write_repo: bool) -> None:
    """Refuse to write into files or non-empty directories."""
    if output_dir.exists():
        if not output_dir.is_dir():
            raise RuntimeError(f"{output_dir} exists and is not a directory.")
        if any(output_dir.iterdir()):
            raise RuntimeError(
                f"{output_dir} is not empty. Refusing to modify an existing folder."
            )
    elif write_repo:
        output_dir.mkdir(parents=True)


def run_git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    command = ["git", *args]
    try:
        result = subprocess.run(
            command,
            cwd=repo,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as error:
        raise RuntimeError("Git was not found on PATH.") from error
    if result.returncode != 0:
        joined = " ".join(command)
        raise RuntimeError(f"{joined} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def git_config_value(key: str, cwd: Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            ["git", "config", "--get", key],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def resolve_contributor(
    author_name: str | None,
    author_email: str | None,
    cwd: Path | None = None,
) -> Contributor:
    name = (author_name or git_config_value("user.name", cwd) or "Grid Graffiti").strip()
    email = (
        author_email
        or git_config_value("user.email", cwd)
        or "grid-graffiti@example.invalid"
    ).strip()

    if not name:
        raise ValueError("Commit author name cannot be empty.")
    if not email:
        raise ValueError("Commit author email cannot be empty.")
    if "@" not in email:
        raise ValueError("Commit author email must contain '@'.")

    return Contributor(name=name, email=email)


def assert_no_remotes(repo: Path) -> None:
    remotes = run_git(repo, "remote")
    if remotes.strip():
        raise RuntimeError(
            "This educational script refuses to operate when a Git remote exists."
        )


def git_timestamp(day: date, hour: int) -> str:
    # Fixed UTC timestamp keeps the demo deterministic across machines.
    moment = datetime.combine(day, time(hour=hour), tzinfo=timezone.utc)
    return moment.isoformat()


def create_local_repo(
    output_dir: Path,
    pixels: Iterable[Pixel],
    commits_per_pixel: int,
    commit_hour: int,
    contributor: Contributor,
) -> int:
    if shutil.which("git") is None:
        raise RuntimeError("Git was not found on PATH.")

    output_dir.mkdir(parents=True, exist_ok=True)
    run_git(output_dir, "init", "-b", "main")
    run_git(output_dir, "config", "user.name", contributor.name)
    run_git(output_dir, "config", "user.email", contributor.email)
    assert_no_remotes(output_dir)

    data_file = output_dir / "pixels.txt"
    commit_count = 0

    for pixel in sorted(pixels, key=lambda p: (p.day, p.row, p.column)):
        for layer in range(1, commits_per_pixel + 1):
            commit_count += 1
            with data_file.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"{commit_count:04d},"
                    f"column={pixel.column},"
                    f"row={pixel.row},"
                    f"day={pixel.day.isoformat()},"
                    f"layer={layer}\n"
                )

            run_git(output_dir, "add", "pixels.txt")

            env = os.environ.copy()
            stamp = git_timestamp(pixel.day, commit_hour)
            env["GIT_AUTHOR_DATE"] = stamp
            env["GIT_COMMITTER_DATE"] = stamp

            run_git(
                output_dir,
                "commit",
                "-m",
                (
                    f"demo pixel col={pixel.column} "
                    f"row={pixel.row} layer={layer}"
                ),
                env=env,
            )

    assert_no_remotes(output_dir)
    return commit_count


def write_csv(path: Path, pixels: Iterable[Pixel], commits_per_pixel: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["column", "row", "weekday", "date", "commits_for_cell"]
        )
        for pixel in sorted(pixels, key=lambda p: (p.column, p.row)):
            writer.writerow(
                [
                    pixel.column,
                    pixel.row,
                    DAY_NAMES[pixel.row],
                    pixel.day.isoformat(),
                    commits_per_pixel,
                ]
            )


def write_svg(
    path: Path,
    text: str,
    reference: date,
    pixels: Iterable[Pixel],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lit = {(pixel.column, pixel.row) for pixel in pixels}
    width = PADDING * 2 + COLUMNS * CELL + (COLUMNS - 1) * GAP
    height = PADDING * 2 + ROWS * CELL + (ROWS - 1) * GAP + 34

    rects: list[str] = []
    for column in range(COLUMNS):
        for row in range(ROWS):
            x = PADDING + column * (CELL + GAP)
            y = PADDING + 28 + row * (CELL + GAP)
            fill = "#39d353" if (column, row) in lit else "#161b22"
            rects.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
                f'rx="2" fill="{fill}"/>'
            )

    title = html.escape(f'{text} — reference date {reference.isoformat()}')
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
    width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" rx="10" fill="#0d1117"/>
  <text x="{PADDING}" y="20" fill="#c9d1d9"
        font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
        font-size="12">{title}</text>
  {''.join(rects)}
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        text = normalise_text(args.text)
        contributor = resolve_contributor(args.author_name, args.author_email, Path.cwd())
        bitmap = text_bitmap(text)
        pixels = lit_pixels(bitmap, args.today, args.align)

        print(f"Text: {text}")
        print(f"Reference date: {args.today.isoformat()}")
        print(f"Commit author: {contributor.name} <{contributor.email}>")
        print(f"Grid starts: {grid_start(args.today).isoformat()} (Sunday)")
        print(f"Current/rightmost week starts: {current_week_sunday(args.today).isoformat()}")
        print(f"Lit cells: {len(pixels)}")
        print()
        print(ascii_preview(bitmap, args.align))
        print()

        if not args.write_repo:
            print("Dry run only. Add --write-repo to create the local demo repository.")
            return 0

        ensure_safe_output_dir(args.output_dir, write_repo=True)

        svg_path = args.output_dir / "grid-preview.svg"
        csv_path = args.output_dir / "grid-dates.csv"

        write_svg(svg_path, text, args.today, pixels)
        write_csv(csv_path, pixels, args.commits_per_pixel)

        commit_count = create_local_repo(
            args.output_dir,
            pixels,
            args.commits_per_pixel,
            args.commit_hour,
            contributor,
        )

        print(f"Created local repository: {args.output_dir.resolve()}")
        print(f"Created commits: {commit_count}")
        print(f"SVG preview: {svg_path.resolve()}")
        print(f"Date manifest: {csv_path.resolve()}")
        print("No remote was added.")
        return 0

    except (ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
