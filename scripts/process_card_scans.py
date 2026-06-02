#!/usr/bin/env python3
"""Deskew and crop one-card scanner images.

The script treats the input directory as read-only. It writes processed
full-size crops, web-sized derivatives, and manifests to the output paths.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from PIL import Image


SUPPORTED_EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class Result:
    source: str
    status: str
    processed: str = ""
    web: str = ""
    source_width: int | None = None
    source_height: int | None = None
    processed_width: int | None = None
    processed_height: int | None = None
    web_width: int | None = None
    web_height: int | None = None
    aspect_ratio: float | None = None
    orientation: str = ""
    rotation_degrees: float | None = None
    imagesrc: str = ""
    image_rect: str = ""
    reason: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deskew/crop raw card scans into processed and web images."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Read-only directory containing one-card scans.",
    )
    parser.add_argument(
        "--processed-dir",
        required=True,
        type=Path,
        help="Output directory for full-size deskewed crops.",
    )
    parser.add_argument(
        "--web-dir",
        required=True,
        type=Path,
        help="Output directory for web-sized derivatives.",
    )
    parser.add_argument(
        "--manifest-dir",
        required=True,
        type=Path,
        help="Output directory for CSV/JSONL processing manifests.",
    )
    parser.add_argument(
        "--processed-format",
        default="png",
        choices=["png", "tif", "tiff", "webp", "jpg", "jpeg"],
        help="Full-size processed output format.",
    )
    parser.add_argument(
        "--web-format",
        default="webp",
        choices=["webp", "jpg", "jpeg", "png"],
        help="Web derivative output format.",
    )
    parser.add_argument(
        "--web-height",
        default=1500,
        type=int,
        help="Maximum height for web derivatives.",
    )
    parser.add_argument(
        "--fuzz",
        default="8%",
        help="ImageMagick fuzz value used for trimming scanner background.",
    )
    parser.add_argument(
        "--deskew-threshold",
        default="40%",
        help="ImageMagick deskew threshold.",
    )
    parser.add_argument(
        "--pad",
        default=16,
        type=int,
        help="Pixels of neutral padding added before final trim/deskew.",
    )
    parser.add_argument(
        "--quality",
        default=92,
        type=int,
        help="Quality for lossy web outputs.",
    )
    parser.add_argument(
        "--min-aspect",
        default=0.64,
        type=float,
        help="Minimum accepted width/height aspect ratio.",
    )
    parser.add_argument(
        "--max-aspect",
        default=0.78,
        type=float,
        help="Maximum accepted width/height aspect ratio.",
    )
    parser.add_argument(
        "--landscape-min-aspect",
        default=1.28,
        type=float,
        help="Minimum accepted width/height aspect ratio for landscape cards.",
    )
    parser.add_argument(
        "--landscape-max-aspect",
        default=1.56,
        type=float,
        help="Maximum accepted width/height aspect ratio for landscape cards.",
    )
    parser.add_argument(
        "--no-landscape",
        action="store_true",
        help="Treat landscape-oriented crops as review items.",
    )
    parser.add_argument(
        "--tight-crop-threshold",
        default=50.0,
        type=float,
        help="Pixel distance from sampled background required for tight crop.",
    )
    parser.add_argument(
        "--tight-crop-min-fraction",
        default=0.02,
        type=float,
        help="Minimum row/column foreground fraction required for tight crop.",
    )
    parser.add_argument(
        "--tight-crop-padding",
        default=0,
        type=int,
        help="Pixels of padding to keep around the detected tight crop.",
    )
    parser.add_argument(
        "--tight-crop-passes",
        default=2,
        type=int,
        help="Number of second-pass pixel crops to apply after deskewing.",
    )
    parser.add_argument(
        "--no-tight-crop",
        action="store_true",
        help="Disable the second-pass pixel crop.",
    )
    parser.add_argument(
        "--edge-refine",
        action="store_true",
        help="Refine crop by detecting scanner-bed/card transitions in side-specific bands.",
    )
    parser.add_argument(
        "--edge-trim-bottom",
        action="store_true",
        help="Also trim the bottom edge during edge refinement. Off by default.",
    )
    parser.add_argument(
        "--edge-bottom-max-trim-pixels",
        default=18,
        type=int,
        help="Maximum pixels to trim from the bottom edge when --edge-trim-bottom is enabled.",
    )
    parser.add_argument(
        "--edge-bottom-max-trim-fraction",
        default=0.006,
        type=float,
        help="Maximum image-height fraction to trim from the bottom edge when enabled.",
    )
    parser.add_argument(
        "--edge-bottom-candidate-max-pixels",
        default=38,
        type=int,
        help="Do not trim the bottom if the detected edge is farther in than this.",
    )
    parser.add_argument(
        "--edge-bottom-min-prominence",
        default=1.12,
        type=float,
        help="Required max/median gradient ratio before trimming the bottom edge.",
    )
    parser.add_argument(
        "--edge-deskew",
        action="store_true",
        help="Refine residual rotation by fitting near-perimeter card edges.",
    )
    parser.add_argument(
        "--edge-band-start",
        default=0.20,
        type=float,
        help="Fractional start of the central band used for edge detection.",
    )
    parser.add_argument(
        "--edge-band-end",
        default=0.80,
        type=float,
        help="Fractional end of the central band used for edge detection.",
    )
    parser.add_argument(
        "--edge-padding",
        default=2,
        type=int,
        help="Pixels to keep outside edge-refined crop bounds.",
    )
    parser.add_argument(
        "--edge-max-trim-fraction",
        default=0.035,
        type=float,
        help="Maximum fraction edge refinement may trim from any one side.",
    )
    parser.add_argument(
        "--edge-max-trim-pixels",
        default=140,
        type=int,
        help="Absolute maximum pixels edge refinement may trim from any one side.",
    )
    parser.add_argument(
        "--edge-gradient-percentile",
        default=85.0,
        type=float,
        help="Gradient percentile used to choose the first likely perimeter edge.",
    )
    parser.add_argument(
        "--edge-min-prominence",
        default=1.03,
        type=float,
        help="Required max/median gradient ratio before trimming a side.",
    )
    parser.add_argument(
        "--edge-deskew-max-angle",
        default=2.0,
        type=float,
        help="Maximum residual rotation, in degrees, accepted by edge deskew.",
    )
    parser.add_argument(
        "--edge-deskew-min-angle",
        default=0.05,
        type=float,
        help="Minimum residual rotation, in degrees, worth applying.",
    )
    parser.add_argument(
        "--edge-deskew-samples",
        default=80,
        type=int,
        help="Number of vertical chunks sampled when fitting edge rotation.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process at most this many scans, useful for test runs.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing processed/web outputs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List work and write no image outputs.",
    )
    parser.add_argument(
        "--refresh-manifest",
        action="store_true",
        help=(
            "Rebuild manifests from existing processed/web outputs without "
            "writing image files."
        ),
    )
    parser.add_argument(
        "--url-base",
        default="",
        help=(
            "Optional base URL for web images. If set, manifests include "
            "imagesrc and image_rect fields for direct card JSON ingestion."
        ),
    )
    parser.add_argument(
        "--edge-overrides",
        type=Path,
        help=(
            "Optional JSON file keyed by scan stem with edge trim deltas, "
            "for example {\"scan65\": {\"left\": -70}}."
        ),
    )
    parser.add_argument(
        "--orientation-overrides",
        type=Path,
        help=(
            "Optional JSON file keyed by scan stem with quarter-turn rotations. "
            "Use 90 for counter-clockwise and -90 for clockwise."
        ),
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


def list_inputs(input_dir: Path, limit: int | None) -> list[Path]:
    files = [
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    files.sort(key=natural_key)
    return files[:limit] if limit else files


def identify_dimensions(path: Path) -> tuple[int, int]:
    output = subprocess.check_output(
        [
            "magick",
            "identify",
            "-format",
            "%w %h",
            str(path),
        ],
        text=True,
    )
    first_line = output.strip().splitlines()[0]
    width, height = first_line.split()[:2]
    return int(width), int(height)


def magick_source(path: Path) -> str:
    # TIFFs often include a second embedded thumbnail. [0] forces the full scan.
    return f"{path}[0]" if path.suffix.lower() in {".tif", ".tiff"} else str(path)


def output_path(directory: Path, source: Path, extension: str) -> Path:
    normalized = "jpg" if extension == "jpeg" else extension
    return directory / f"{source.stem}.{normalized}"


def load_edge_overrides(path: Path | None) -> dict[str, dict[str, int]]:
    if path is None:
        return {}
    with path.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    overrides: dict[str, dict[str, int]] = {}
    for stem, values in raw.items():
        if not isinstance(values, dict):
            raise ValueError(f"Override for {stem} must be an object")
        side_values: dict[str, int] = {}
        for side in ("left", "right", "top", "bottom"):
            if side in values:
                side_values[side] = int(values[side])
        overrides[str(stem)] = side_values
    return overrides


def load_orientation_overrides(path: Path | None) -> dict[str, int]:
    if path is None:
        return {}
    with path.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    overrides: dict[str, int] = {}
    for stem, values in raw.items():
        if isinstance(values, dict):
            value = values.get("rotate_degrees", values.get("rotate"))
        else:
            value = values
        degrees = int(value)
        if degrees not in {-270, -180, -90, 0, 90, 180, 270}:
            raise ValueError(
                f"Orientation override for {stem} must be a quarter-turn, got {degrees}"
            )
        overrides[str(stem)] = degrees
    return overrides


def processed_command(source: Path, dest: Path, args: argparse.Namespace) -> list[str]:
    return [
        "magick",
        magick_source(source),
        "-auto-orient",
        "-alpha",
        "off",
        "-bordercolor",
        "white",
        "-border",
        str(args.pad),
        "-deskew",
        args.deskew_threshold,
        "-fuzz",
        args.fuzz,
        "-trim",
        "+repage",
        "-strip",
        str(dest),
    ]


def web_command(source: Path, dest: Path, args: argparse.Namespace) -> list[str]:
    command = [
        "magick",
        str(source),
        "-auto-orient",
        "-resize",
        f"x{args.web_height}>",
        "-strip",
    ]
    if dest.suffix.lower() in {".jpg", ".jpeg", ".webp"}:
        command.extend(["-quality", str(args.quality)])
    command.append(str(dest))
    return command


def tight_crop(path: Path, args: argparse.Namespace) -> tuple[int, int]:
    with Image.open(path) as image:
        original_format = image.format
        rgb = image.convert("RGB")

    pixels = np.asarray(rgb).astype(np.int16)
    height, width = pixels.shape[:2]
    sample_size = max(20, min(width, height) // 50)
    corners = np.concatenate(
        [
            pixels[:sample_size, :sample_size].reshape(-1, 3),
            pixels[:sample_size, -sample_size:].reshape(-1, 3),
            pixels[-sample_size:, :sample_size].reshape(-1, 3),
            pixels[-sample_size:, -sample_size:].reshape(-1, 3),
        ],
        axis=0,
    )
    background = np.median(corners, axis=0)
    distance = np.sqrt(((pixels - background) ** 2).sum(axis=2))
    foreground = distance > args.tight_crop_threshold

    rows = np.where(foreground.mean(axis=1) > args.tight_crop_min_fraction)[0]
    cols = np.where(foreground.mean(axis=0) > args.tight_crop_min_fraction)[0]
    if len(rows) == 0 or len(cols) == 0:
        return width, height

    pad = max(0, args.tight_crop_padding)
    left = max(0, int(cols[0]) - pad)
    top = max(0, int(rows[0]) - pad)
    right = min(width, int(cols[-1]) + 1 + pad)
    bottom = min(height, int(rows[-1]) + 1 + pad)

    if right <= left or bottom <= top:
        return width, height

    cropped = rgb.crop((left, top, right, bottom))
    save_kwargs = {}
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        save_kwargs["quality"] = 95
    cropped.save(path, format=original_format, **save_kwargs)
    return cropped.size


def first_perimeter_gradient(
    profile: np.ndarray,
    args: argparse.Namespace,
    min_prominence: float | None = None,
) -> int:
    if len(profile) == 0:
        return 0
    smooth_width = min(7, len(profile))
    kernel = np.ones(smooth_width) / smooth_width
    smoothed = np.convolve(profile, kernel, mode="same")
    median = float(np.median(smoothed))
    peak = float(np.max(smoothed))
    prominence = args.edge_min_prominence if min_prominence is None else min_prominence
    if median <= 0 or peak / median < prominence:
        return 0
    percentile = min(max(args.edge_gradient_percentile, 50.0), 99.0)
    threshold = float(np.percentile(smoothed, percentile))
    candidates = np.where(smoothed >= threshold)[0]
    if len(candidates) == 0:
        return 0
    return int(candidates[0])


def edge_refine_crop(path: Path, args: argparse.Namespace) -> tuple[int, int]:
    with Image.open(path) as image:
        original_format = image.format
        rgb = image.convert("RGB")

    grayscale = np.asarray(rgb.convert("L")).astype(np.float32)
    height, width = grayscale.shape
    gradient_y, gradient_x = np.gradient(grayscale)
    gradient_y = np.abs(gradient_y)
    gradient_x = np.abs(gradient_x)

    band_start = min(max(args.edge_band_start, 0.05), 0.45)
    band_end = min(max(args.edge_band_end, 0.55), 0.95)
    x1 = int(width * band_start)
    x2 = int(width * band_end)
    y1 = int(height * band_start)
    y2 = int(height * band_end)

    max_x_trim = max(
        1,
        min(
            int(width * max(0.0, args.edge_max_trim_fraction)),
            max(1, args.edge_max_trim_pixels),
        ),
    )
    max_y_trim = max(
        1,
        min(
            int(height * max(0.0, args.edge_max_trim_fraction)),
            max(1, args.edge_max_trim_pixels),
        ),
    )

    top_profile = gradient_y[:max_y_trim, x1:x2].mean(axis=1)
    bottom_profile = gradient_y[-max_y_trim:, x1:x2].mean(axis=1)[::-1]
    left_profile = gradient_x[y1:y2, :max_x_trim].mean(axis=0)
    right_profile = gradient_x[y1:y2, -max_x_trim:].mean(axis=0)[::-1]

    pad = max(0, args.edge_padding)
    top_trim = max(0, first_perimeter_gradient(top_profile, args) - pad)
    if args.edge_trim_bottom:
        bottom_candidate = first_perimeter_gradient(
            bottom_profile,
            args,
            min_prominence=args.edge_bottom_min_prominence,
        )
        max_bottom_trim = max(
            0,
            min(
                args.edge_bottom_max_trim_pixels,
                int(height * max(0.0, args.edge_bottom_max_trim_fraction)),
            ),
        )
        if bottom_candidate <= args.edge_bottom_candidate_max_pixels:
            bottom_trim = min(max_bottom_trim, max(0, bottom_candidate - pad))
        else:
            bottom_trim = 0
    else:
        bottom_trim = 0
    left_trim = max(0, first_perimeter_gradient(left_profile, args) - pad)
    right_trim = max(0, first_perimeter_gradient(right_profile, args) - pad)

    overrides = getattr(args, "edge_overrides_data", {}).get(path.stem, {})
    left_trim += int(overrides.get("left", 0))
    right_trim += int(overrides.get("right", 0))
    top_trim += int(overrides.get("top", 0))
    bottom_trim += int(overrides.get("bottom", 0))

    left_trim = max(0, min(left_trim, max_x_trim))
    right_trim = max(0, min(right_trim, max_x_trim))
    top_trim = max(0, min(top_trim, max_y_trim))
    bottom_trim = max(0, min(bottom_trim, max_y_trim))

    left = left_trim
    top = top_trim
    right = width - right_trim
    bottom = height - bottom_trim

    if right <= left or bottom <= top:
        return width, height

    cropped = rgb.crop((left, top, right, bottom))
    save_kwargs = {}
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        save_kwargs["quality"] = 95
    cropped.save(path, format=original_format, **save_kwargs)
    return cropped.size


def edge_position(profile: np.ndarray, args: argparse.Namespace) -> int | None:
    if len(profile) == 0:
        return None
    smooth_width = min(7, len(profile))
    kernel = np.ones(smooth_width) / smooth_width
    smoothed = np.convolve(profile, kernel, mode="same")
    median = float(np.median(smoothed))
    peak = float(np.max(smoothed))
    if median <= 0 or peak / median < args.edge_min_prominence:
        return None
    percentile = min(max(args.edge_gradient_percentile, 50.0), 99.0)
    threshold = float(np.percentile(smoothed, percentile))
    candidates = np.where(smoothed >= threshold)[0]
    if len(candidates) == 0:
        return None
    return int(candidates[0])


def fit_residual_rotation(path: Path, args: argparse.Namespace) -> float | None:
    with Image.open(path) as image:
        grayscale = np.asarray(image.convert("L")).astype(np.float32)

    height, width = grayscale.shape
    gradient_y, gradient_x = np.gradient(grayscale)
    gradient_y = np.abs(gradient_y)
    gradient_x = np.abs(gradient_x)

    x_start = int(width * 0.12)
    x_end = int(width * 0.88)
    y_start = int(height * 0.12)
    y_end = int(height * 0.88)
    if x_end <= x_start or y_end <= y_start:
        return None

    max_y_trim = max(
        1,
        min(
            int(height * max(0.0, args.edge_max_trim_fraction)),
            max(1, args.edge_max_trim_pixels),
        ),
    )
    samples = max(8, args.edge_deskew_samples)
    x_chunk_edges = np.linspace(x_start, x_end, samples + 1, dtype=int)
    y_chunk_edges = np.linspace(y_start, y_end, samples + 1, dtype=int)
    top_points: list[tuple[float, float]] = []
    bottom_points: list[tuple[float, float]] = []
    left_points: list[tuple[float, float]] = []
    right_points: list[tuple[float, float]] = []

    for left, right in zip(x_chunk_edges[:-1], x_chunk_edges[1:]):
        if right <= left:
            continue
        x_mid = (left + right) / 2
        top_profile = gradient_y[:max_y_trim, left:right].mean(axis=1)
        bottom_profile = gradient_y[-max_y_trim:, left:right].mean(axis=1)[::-1]

        top_y = edge_position(top_profile, args)
        if top_y is not None:
            top_points.append((x_mid, float(top_y)))

        bottom_from_end = edge_position(bottom_profile, args)
        if bottom_from_end is not None:
            bottom_points.append((x_mid, float(height - 1 - bottom_from_end)))

    max_x_trim = max(
        1,
        min(
            int(width * max(0.0, args.edge_max_trim_fraction)),
            max(1, args.edge_max_trim_pixels),
        ),
    )
    for top, bottom in zip(y_chunk_edges[:-1], y_chunk_edges[1:]):
        if bottom <= top:
            continue
        y_mid = (top + bottom) / 2
        left_profile = gradient_x[top:bottom, :max_x_trim].mean(axis=0)
        right_profile = gradient_x[top:bottom, -max_x_trim:].mean(axis=0)[::-1]

        left_x = edge_position(left_profile, args)
        if left_x is not None:
            left_points.append((y_mid, float(left_x)))

        right_from_end = edge_position(right_profile, args)
        if right_from_end is not None:
            right_points.append((y_mid, float(width - 1 - right_from_end)))

    slopes: list[float] = []
    min_points = max(8, samples // 5)
    for points in (top_points, bottom_points):
        if len(points) < min_points:
            continue
        xs = np.array([point[0] for point in points])
        ys = np.array([point[1] for point in points])
        slope, intercept = np.polyfit(xs, ys, 1)
        residuals = ys - (slope * xs + intercept)
        keep = np.abs(residuals) <= max(6.0, float(np.percentile(np.abs(residuals), 75)) * 2.5)
        if int(keep.sum()) >= min_points:
            slope, _ = np.polyfit(xs[keep], ys[keep], 1)
            slopes.append(float(slope))

    for points in (left_points, right_points):
        if len(points) < min_points:
            continue
        ys = np.array([point[0] for point in points])
        xs = np.array([point[1] for point in points])
        slope, intercept = np.polyfit(ys, xs, 1)
        residuals = xs - (slope * ys + intercept)
        keep = np.abs(residuals) <= max(6.0, float(np.percentile(np.abs(residuals), 75)) * 2.5)
        if int(keep.sum()) >= min_points:
            slope, _ = np.polyfit(ys[keep], xs[keep], 1)
            slopes.append(float(-slope))

    if not slopes:
        return None
    angle = float(np.degrees(np.arctan(np.median(slopes))))
    if abs(angle) < args.edge_deskew_min_angle:
        return 0.0
    if abs(angle) > args.edge_deskew_max_angle:
        return None
    return angle


def edge_deskew(path: Path, args: argparse.Namespace) -> float | None:
    angle = fit_residual_rotation(path, args)
    if angle is None or angle == 0.0:
        return angle

    with Image.open(path) as image:
        original_format = image.format
        rgb = image.convert("RGB")

    rotated = rgb.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(255, 255, 255),
    )
    save_kwargs = {}
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        save_kwargs["quality"] = 95
    rotated.save(path, format=original_format, **save_kwargs)
    return round(angle, 4)


def apply_orientation_override(path: Path, source: Path, args: argparse.Namespace) -> int:
    degrees = args.orientation_overrides_data.get(source.stem, 0)
    if degrees == 0:
        return 0

    with Image.open(path) as image:
        original_format = image.format
        rgb = image.convert("RGB")

    rotated = rgb.rotate(
        degrees,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(255, 255, 255),
    )
    save_kwargs = {}
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        save_kwargs["quality"] = 95
    rotated.save(path, format=original_format, **save_kwargs)
    return degrees


def validate(result: Result, args: argparse.Namespace) -> Result:
    if result.processed_width is None or result.processed_height is None:
        result.status = "review"
        result.reason = result.reason or "missing processed dimensions"
        return result
    if result.processed_height == 0:
        result.status = "review"
        result.reason = "invalid processed height"
        return result
    ratio = result.processed_width / result.processed_height
    result.aspect_ratio = round(ratio, 4)
    result.orientation = "landscape" if ratio > 1 else "portrait"
    if result.orientation == "landscape" and not args.no_landscape:
        min_aspect = args.landscape_min_aspect
        max_aspect = args.landscape_max_aspect
    else:
        min_aspect = args.min_aspect
        max_aspect = args.max_aspect
    if ratio < min_aspect or ratio > max_aspect:
        result.status = "review"
        result.reason = (
            f"aspect ratio {ratio:.4f} outside "
            f"{min_aspect:.2f}-{max_aspect:.2f}"
        )
    return result


def refresh_existing_outputs(result: Result, processed: Path, web: Path, args: argparse.Namespace) -> Result:
    if not processed.exists():
        result.status = "error"
        result.reason = f"missing processed output: {processed}"
        return result
    if not web.exists():
        result.status = "error"
        result.reason = f"missing web output: {web}"
        return result
    result.processed_width, result.processed_height = identify_dimensions(processed)
    result.web_width, result.web_height = identify_dimensions(web)
    validate(result, args)
    return result


def process_one(source: Path, args: argparse.Namespace) -> Result:
    processed = output_path(args.processed_dir, source, args.processed_format)
    web = output_path(args.web_dir, source, args.web_format)
    result = Result(source=str(source), status="ok", processed=str(processed), web=str(web))
    if args.url_base:
        result.imagesrc = f"{args.url_base.rstrip('/')}/{web.name}"
        result.image_rect = "[0,1,1]"

    try:
        result.source_width, result.source_height = identify_dimensions(Path(magick_source(source)))
    except Exception:
        # identify cannot receive the Path-with-[0] form; fall back to source path.
        try:
            result.source_width, result.source_height = identify_dimensions(source)
        except Exception as exc:
            result.status = "error"
            result.reason = f"could not identify source: {exc}"
            return result

    if args.dry_run:
        result.status = "dry-run"
        return result

    if args.refresh_manifest:
        return refresh_existing_outputs(result, processed, web, args)

    if not args.force and (processed.exists() or web.exists()):
        refresh_existing_outputs(result, processed, web, args)
        if result.status == "ok":
            result.status = "skipped"
            result.reason = "output exists; use --force to overwrite"
        return result

    try:
        subprocess.run(processed_command(source, processed, args), check=True)
        if not args.no_tight_crop:
            for _ in range(max(1, args.tight_crop_passes)):
                before = identify_dimensions(processed)
                after = tight_crop(processed, args)
                if after == before:
                    break
        if args.edge_deskew:
            result.rotation_degrees = edge_deskew(processed, args)
            if result.rotation_degrees:
                for _ in range(max(1, args.tight_crop_passes)):
                    before = identify_dimensions(processed)
                    after = tight_crop(processed, args)
                    if after == before:
                        break
        if args.edge_refine:
            edge_refine_crop(processed, args)
        orientation_rotation = apply_orientation_override(processed, source, args)
        result.processed_width, result.processed_height = identify_dimensions(processed)
        validate(result, args)
        if orientation_rotation:
            override_reason = f"orientation override rotate {orientation_rotation}"
            result.reason = (
                f"{result.reason}; {override_reason}" if result.reason else override_reason
            )
        subprocess.run(web_command(processed, web, args), check=True)
        result.web_width, result.web_height = identify_dimensions(web)
    except subprocess.CalledProcessError as exc:
        result.status = "error"
        result.reason = f"ImageMagick failed: {exc}"
    except Exception as exc:
        result.status = "error"
        result.reason = str(exc)
    return result


def write_manifests(results: list[Result], manifest_dir: Path) -> None:
    manifest_dir.mkdir(parents=True, exist_ok=True)
    csv_path = manifest_dir / "process_manifest.csv"
    jsonl_path = manifest_dir / "process_manifest.jsonl"
    fields = list(asdict(results[0]).keys()) if results else list(Result("", "").__dict__.keys())

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    require_magick()
    args.edge_overrides_data = load_edge_overrides(args.edge_overrides)
    args.orientation_overrides_data = load_orientation_overrides(args.orientation_overrides)

    if not args.input_dir.is_dir():
        print(f"Input directory does not exist: {args.input_dir}", file=sys.stderr)
        return 2

    if args.input_dir.resolve() in {
        args.processed_dir.resolve(),
        args.web_dir.resolve(),
        args.manifest_dir.resolve(),
    }:
        print("Refusing to use the raw input directory as an output directory.", file=sys.stderr)
        return 2

    if not args.dry_run:
        args.processed_dir.mkdir(parents=True, exist_ok=True)
        args.web_dir.mkdir(parents=True, exist_ok=True)
        args.manifest_dir.mkdir(parents=True, exist_ok=True)

    inputs = list_inputs(args.input_dir, args.limit)
    if not inputs:
        print(f"No supported image files found in {args.input_dir}", file=sys.stderr)
        return 1

    results: list[Result] = []
    for index, source in enumerate(inputs, start=1):
        result = process_one(source, args)
        results.append(result)
        detail = f" ({result.reason})" if result.reason else ""
        print(f"[{index}/{len(inputs)}] {source.name}: {result.status}{detail}", flush=True)

    if not args.dry_run:
        write_manifests(results, args.manifest_dir)

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    print(
        "Summary:",
        ", ".join(f"{status}={count}" for status, count in sorted(counts.items())),
        flush=True,
    )
    return 0 if not any(r.status == "error" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
