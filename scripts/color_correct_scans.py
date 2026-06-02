#!/usr/bin/env python3
"""Generate color-corrected web derivatives from processed card crops."""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {".png", ".tif", ".tiff", ".jpg", ".jpeg", ".webp"}


@dataclass
class Result:
    source: str
    status: str
    output: str = ""
    saturation: int | None = None
    contrast: int | None = None
    brightness: int | None = None
    reason: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create color-corrected web images from processed card crops."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory containing processed full-size card crops.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for color-corrected web derivatives.",
    )
    parser.add_argument(
        "--format",
        default="webp",
        choices=["webp", "jpg", "jpeg", "png"],
        help="Output image format.",
    )
    parser.add_argument(
        "--web-height",
        default=1500,
        type=int,
        help="Maximum height for web derivatives.",
    )
    parser.add_argument(
        "--quality",
        default=92,
        type=int,
        help="Quality for lossy outputs.",
    )
    parser.add_argument(
        "--saturation",
        default=115,
        type=int,
        help="ImageMagick modulate saturation percentage.",
    )
    parser.add_argument(
        "--brightness",
        default=100,
        type=int,
        help="ImageMagick modulate brightness percentage.",
    )
    parser.add_argument(
        "--hue",
        default=100,
        type=int,
        help="ImageMagick modulate hue percentage.",
    )
    parser.add_argument(
        "--contrast",
        default=4,
        type=int,
        help="ImageMagick brightness-contrast contrast value.",
    )
    parser.add_argument(
        "--contrast-brightness",
        default=0,
        type=int,
        help="ImageMagick brightness-contrast brightness value.",
    )
    parser.add_argument(
        "--stems",
        help="Comma-separated scan stems to process, for example scan00,scan09.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process at most this many images after sorting/filtering.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output images.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List work and write no images.",
    )
    return parser.parse_args()


def require_magick() -> None:
    if shutil.which("magick") is None:
        raise SystemExit(
            "ImageMagick 7 is required. Install it so the `magick` command is available."
        )


def natural_key(path: Path) -> tuple[str, int]:
    stem = path.stem
    digits = ""
    for char in reversed(stem):
        if char.isdigit():
            digits = char + digits
        else:
            break
    return (stem[: -len(digits)] if digits else stem, int(digits or 0))


def list_inputs(input_dir: Path, stems: str | None, limit: int | None) -> list[Path]:
    wanted = {stem.strip() for stem in stems.split(",") if stem.strip()} if stems else None
    files = [
        path
        for path in input_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and (wanted is None or path.stem in wanted)
    ]
    files.sort(key=natural_key)
    return files[:limit] if limit else files


def output_path(output_dir: Path, source: Path, suffix: str) -> Path:
    return output_dir / f"{source.stem}.{suffix.lstrip('.')}"


def color_command(source: Path, output: Path, args: argparse.Namespace) -> list[str]:
    command = [
        "magick",
        str(source),
        "-auto-orient",
        "-modulate",
        f"{args.brightness},{args.saturation},{args.hue}",
        "-brightness-contrast",
        f"{args.contrast_brightness}x{args.contrast}",
        "-resize",
        f"x{args.web_height}>",
        "-strip",
    ]
    if output.suffix.lower() in {".jpg", ".jpeg", ".webp"}:
        command.extend(["-quality", str(args.quality)])
    command.append(str(output))
    return command


def process_one(source: Path, args: argparse.Namespace) -> Result:
    output = output_path(args.output_dir, source, args.format)
    result = Result(
        source=str(source),
        status="ok",
        output=str(output),
        saturation=args.saturation,
        contrast=args.contrast,
        brightness=args.brightness,
    )

    if args.dry_run:
        result.status = "dry-run"
        return result
    if output.exists() and not args.force:
        result.status = "skipped"
        result.reason = "output exists; use --force to overwrite"
        return result

    try:
        subprocess.run(color_command(source, output, args), check=True)
    except subprocess.CalledProcessError as exc:
        result.status = "error"
        result.reason = f"ImageMagick failed: {exc}"
    return result


def write_manifest(results: list[Result], output_dir: Path) -> None:
    path = output_dir / "color_manifest.csv"
    fields = list(asdict(results[0]).keys()) if results else list(Result("", "").__dict__)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))


def main() -> int:
    args = parse_args()
    require_magick()
    if not args.input_dir.is_dir():
        print(f"Input directory does not exist: {args.input_dir}", file=sys.stderr)
        return 2
    if not args.dry_run:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    inputs = list_inputs(args.input_dir, args.stems, args.limit)
    if not inputs:
        print(f"No supported images found in {args.input_dir}", file=sys.stderr)
        return 1

    results = []
    for index, source in enumerate(inputs, start=1):
        result = process_one(source, args)
        results.append(result)
        detail = f" ({result.reason})" if result.reason else ""
        print(f"[{index}/{len(inputs)}] {source.name}: {result.status}{detail}", flush=True)

    if not args.dry_run:
        write_manifest(results, args.output_dir)

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    print(
        "Summary:",
        ", ".join(f"{status}={count}" for status, count in sorted(counts.items())),
        flush=True,
    )
    return 0 if not any(result.status == "error" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
