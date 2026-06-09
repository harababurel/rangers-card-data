# Scan Processing Workflow

Raw scanner output is treated as read-only. Do not modify or delete files in
`/mnt/stu/media/ebr-scans/raw`.

## Current State

This workflow was tuned against Epson V800/SilverFast TIFF scans in:

```text
/mnt/stu/media/ebr-scans/raw
```

The raw TIFFs are source-of-truth and must stay read-only. The best current
geometry settings were validated on a 20-card sample in:

```text
/mnt/stu/media/ebr-scans/edge-selectbottom38-rot-test/web
/mnt/stu/media/ebr-scans/edge-selectbottom38-rot-test/processed
/mnt/stu/media/ebr-scans/edge-selectbottom38-rot-test/manifests
```

The 20-card test was visually accepted: rotation looked good, margins were
good, and selective bottom trimming fixed `scan00` and `scan05` without
over-cropping `scan09`.

After the full run, four side-edge outliers were identified and handled with
per-scan trim overrides in `docs/scan_edge_overrides.json`:

- `scan65`: left edge was cut too tightly, so the left crop is expanded.
- `scan89`: left edge had a little extra margin, so the left crop is tightened.
- `scan118`: right edge was cut too tightly, so the right crop is expanded.
- `scan124`: right edge had a little extra margin, so the right crop is tightened.

## Process Scans

Create these NAS directories first:

```bash
mkdir -p /mnt/stu/media/ebr-scans/processed
mkdir -p /mnt/stu/media/ebr-scans/web
mkdir -p /mnt/stu/media/ebr-scans/manifests
```

Run a small test batch:

```bash
python3 scripts/process_card_scans.py \
  --input-dir /mnt/stu/media/ebr-scans/raw \
  --processed-dir /mnt/stu/media/ebr-scans/processed \
  --web-dir /mnt/stu/media/ebr-scans/web \
  --manifest-dir /mnt/stu/media/ebr-scans/manifests \
  --url-base http://localhost:8765 \
  --limit 5
```

If the outputs look good, run the full batch:

```bash
python3 scripts/process_card_scans.py \
  --input-dir /mnt/stu/media/ebr-scans/raw \
  --processed-dir /mnt/stu/media/ebr-scans/processed \
  --web-dir /mnt/stu/media/ebr-scans/web \
  --manifest-dir /mnt/stu/media/ebr-scans/manifests \
  --url-base http://localhost:8765 \
  --force \
  --edge-refine \
  --edge-deskew \
  --edge-trim-bottom \
  --edge-overrides docs/scan_edge_overrides.json \
  --orientation-overrides docs/scan_orientation_overrides.json
```

The script writes:

- full-size crops to `processed/`
- web-sized derivatives to `web/`
- `process_manifest.csv` and `process_manifest.jsonl` to `manifests/`

Rows with `status` set to `review` need manual inspection. They are usually
aspect-ratio or trim-confidence issues.

`--edge-overrides` is only for known outliers after visual review. Negative
values expand the crop on that side, and positive values trim more from that
side. Keep the raw scans unchanged and rerun derived outputs when an override
changes.

`--orientation-overrides` is for known cards whose intended orientation cannot
be inferred from the current portrait-shaped crop. Use `90` for a
counter-clockwise quarter turn and `-90` for a clockwise quarter turn. The
current landscape overrides are:

- `scan00`-`scan03`: rotate `90` degrees counter-clockwise.
- `scan04`-`scan07`: rotate `-90` degrees clockwise.
- `scan157`-`scan163`: rotate `90` degrees counter-clockwise.
- `scan165`-`scan171`: rotate `-90` degrees clockwise.

## Rebuild The Manifest

After targeted reruns, rebuild the full manifest from the existing derived
outputs instead of recropping every scan:

```bash
python3 scripts/process_card_scans.py \
  --input-dir /mnt/stu/media/ebr-scans/raw \
  --processed-dir /mnt/stu/media/ebr-scans/processed \
  --web-dir /mnt/stu/media/ebr-scans/web \
  --manifest-dir /mnt/stu/media/ebr-scans/manifests \
  --url-base http://localhost:8765 \
  --refresh-manifest
```

This reads the existing `processed/` and `web/` files, records dimensions,
`imagesrc`, and `image_rect`, and writes fresh manifest files. It does not write
image files.

Some location cards are landscape-oriented. The script records an `orientation`
column and accepts both portrait and landscape card ratios during validation:

- portrait default width/height ratio: `0.64-0.78`
- landscape default width/height ratio: `1.28-1.56`

Use `--no-landscape` only when processing a batch that should contain no
landscape cards and landscape outputs should be flagged for review.

If the landscape cards need to be regenerated after changing orientation
overrides, rerun only those raw scans into the real output directories with
`--force`, the normal geometry options, and
`--orientation-overrides docs/scan_orientation_overrides.json`.

If existing outputs need to be replaced, add `--force`:

```bash
python3 scripts/process_card_scans.py \
  --input-dir /mnt/stu/media/ebr-scans/raw \
  --processed-dir /mnt/stu/media/ebr-scans/processed \
  --web-dir /mnt/stu/media/ebr-scans/web \
  --manifest-dir /mnt/stu/media/ebr-scans/manifests \
  --url-base http://localhost:8765 \
  --force
```

The default crop uses a second pixel-based pass after deskewing. If a future
batch crops too tightly or too loosely, tune:

- `--tight-crop-threshold`: higher values crop more aggressively
- `--tight-crop-min-fraction`: higher values ignore thinner edge details
- `--tight-crop-padding`: keeps extra pixels around the detected card
- `--tight-crop-passes`: repeats the pixel crop; default is `2`

For perimeter-gradient trimming of the top, left, and right edges, add
`--edge-refine`. Test it on a small batch first:

```bash
python3 scripts/process_card_scans.py \
  --input-dir /mnt/stu/media/ebr-scans/raw \
  --processed-dir /mnt/stu/media/ebr-scans/edge-test/processed \
  --web-dir /mnt/stu/media/ebr-scans/edge-test/web \
  --manifest-dir /mnt/stu/media/ebr-scans/edge-test/manifests \
  --url-base http://localhost:8765 \
  --limit 10 \
  --force \
  --edge-refine
```

Edge refinement is intentionally conservative. It searches a narrow outer band
on the top, left, and right edges and limits how far any one side can be
trimmed. Bottom-edge trimming is off by default; add `--edge-trim-bottom` only
for a test batch. When enabled, bottom trimming has stricter prominence checks
and a small cap so cards with good lower edges are left alone.

The current accepted bottom-trim tuning is:

- `--edge-bottom-candidate-max-pixels 38`
- `--edge-bottom-max-trim-pixels 18`
- `--edge-bottom-max-trim-fraction 0.006`
- `--edge-bottom-min-prominence 1.12`

These are the script defaults. This tuning was chosen because a 32 px candidate
cutoff left `scan00` and `scan05` with too much bottom margin, while an
unconditional bottom trim over-cropped `scan09`.

If cards still show a small residual rotation after ImageMagick deskewing, add
`--edge-deskew` to fit the near-perimeter top/bottom card edges and rotate by
the remaining sub-degree angle:

```bash
python3 scripts/process_card_scans.py \
  --input-dir /mnt/stu/media/ebr-scans/raw \
  --processed-dir /mnt/stu/media/ebr-scans/edge-nobottom-rot-test/processed \
  --web-dir /mnt/stu/media/ebr-scans/edge-nobottom-rot-test/web \
  --manifest-dir /mnt/stu/media/ebr-scans/edge-nobottom-rot-test/manifests \
  --url-base http://localhost:8765 \
  --limit 10 \
  --force \
  --edge-refine \
  --edge-deskew
```

The current `--edge-deskew` also considers left/right vertical edges, because
some cards showed a narrow white wedge on the upper part of the left edge after
plain ImageMagick deskewing. Typical accepted residual corrections in testing
were sub-degree values such as `-0.15`, `0.10`, or `0.29` degrees.

## Test Folders

Several NAS folders were created while tuning. They are useful historical
references, but `edge-selectbottom38-rot-test` is the current best sample.

- `/mnt/stu/media/ebr-scans/edge-test`: early edge crop test; later overwritten with bottom trimming and became too aggressive for some cards.
- `/mnt/stu/media/ebr-scans/edge-rot-test`: edge crop plus initial rotation correction; still had aggressive bottom trimming for `scan09`.
- `/mnt/stu/media/ebr-scans/edge-nobottom-rot-test`: rotation correction with bottom trimming disabled; preserved `scan09` but left `scan00` and `scan05` slightly loose at bottom.
- `/mnt/stu/media/ebr-scans/edge-selectbottom-rot-test`: selective bottom trim with a 32 px candidate cutoff; still left `scan00` and `scan05` loose.
- `/mnt/stu/media/ebr-scans/edge-selectbottom38-rot-test`: current best 20-card sample; selective bottom trim cutoff raised to 38 px.

## Validation Checklist

After a full run, inspect:

- `process_manifest.csv` for `review` or `error` statuses.
- `rotation_degrees` for unusually large values; most good corrections should
  be small sub-degree values.
- a mixed visual sample of at least 20-30 cards.
- bottom edges, especially cards similar to `scan09`, to make sure footer text
  and copyright lines are not cut.
- left edges near the top, checking for narrow white wedges.

Helpful manifest checks:

```bash
rg -n ',(review|error),' /mnt/stu/media/ebr-scans/manifests/process_manifest.csv
```

```bash
python3 - <<'PY'
import csv
rows = list(csv.DictReader(open('/mnt/stu/media/ebr-scans/manifests/process_manifest.csv')))
for row in rows:
    angle = row.get('rotation_degrees')
    if angle and angle not in ('0.0', '0'):
        print(row['source'].split('/')[-1], angle, row['aspect_ratio'])
PY
```

## Color Correction

Do color correction after geometry processing. Do not apply saturation or
contrast changes before crop/deskew detection; color changes can affect edge
detection.

Recommended next step is to keep `/processed` as the clean archival crop and
generate separate color-test web derivatives from it. Start with mild global
ImageMagick presets.

Use `scripts/color_correct_scans.py` for reproducible tests. A good mixed
sample is:

```text
scan00,scan04,scan08,scan09,scan20,scan35,scan50,scan65,scan75,scan89,scan100,scan118,scan124,scan140
```

Generate three candidate folders:

```bash
SAMPLES=scan00,scan04,scan08,scan09,scan20,scan35,scan50,scan65,scan75,scan89,scan100,scan118,scan124,scan140

# mild
python3 scripts/color_correct_scans.py \
  --input-dir /mnt/stu/media/ebr-scans/processed \
  --output-dir /mnt/stu/media/ebr-scans/color-test/mild \
  --stems "$SAMPLES" \
  --saturation 110 \
  --contrast 3 \
  --force

# stronger
python3 scripts/color_correct_scans.py \
  --input-dir /mnt/stu/media/ebr-scans/processed \
  --output-dir /mnt/stu/media/ebr-scans/color-test/normal \
  --stems "$SAMPLES" \
  --saturation 115 \
  --contrast 4 \
  --force

# strongest test
python3 scripts/color_correct_scans.py \
  --input-dir /mnt/stu/media/ebr-scans/processed \
  --output-dir /mnt/stu/media/ebr-scans/color-test/strong \
  --stems "$SAMPLES" \
  --saturation 120 \
  --contrast 5 \
  --force
```

The likely default is the normal preset: saturation 115%, contrast +4,
brightness unchanged. Tune using a mixed set of location, mission, moment,
weather, dark green, red/orange, and pale parchment cards rather than a single
card.

## Serve Images Locally

For local curator/parser work:

```bash
cd /mnt/stu/media/ebr-scans/web
python3 -m http.server 8765
```

Single-card processed images use:

```json
"imagesrc": "http://localhost:8765/scan00.webp",
"image_rect": [0, 1, 1]
```

Do not commit `localhost` or `/mnt/stu/...` image sources to final pack JSON.
Use them only while transcribing and validating. Replace them with stable public
HTTPS URLs before final merge if the cards need durable image references.
