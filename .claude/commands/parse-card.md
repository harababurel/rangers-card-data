Parse a path card from images and integrate it into the card database, step by step.

This skill is scoped to **path cards only** (`category_id: "path"`). Other categories (location, weather, mission, challenge, ranger) are out of scope — refuse and ask the user to switch tools if they hand you something else.

## Target pack
If `$ARGUMENTS` names a pack (e.g. "loa", "sotv", or `packs/loa/loa.json`), use that file. Otherwise default to `packs/loa/loa.json` — that's where active work is happening. The pack prefix for IDs is the 2-digit zero-padded `position` of that pack in `packs.json` (e.g. loa → `02`).

## Step 1 — Load card image
Ask the user for:
- `imagesrc`: the Steam CDN URL of the card sprite sheet
- `image_rect`: the three-element array `[card_index, grid_cols, grid_rows]`

(If the user already pasted both values in the `/parse-card` invocation message, use them directly — do not ask again.)

Once you have both values, fetch and crop the card using the Bash tool:

```python
from PIL import Image
import urllib.request, hashlib

imagesrc = "<URL>"
idx, cols, rows = <image_rect>

# Unique paths per (imagesrc, idx) so parallel agents don't collide
token = hashlib.md5(f"{imagesrc}{idx}".encode()).hexdigest()[:8]
sheet_path = f"/tmp/card_sheet_{token}.jpg"
crop_path = f"/tmp/card_crop_{token}.png"

urllib.request.urlretrieve(imagesrc, sheet_path)
img = Image.open(sheet_path)
W, H = img.size
card_w = W // cols
card_h = H // rows
col = idx % cols
row = idx // cols
cropped = img.crop((col * card_w, row * card_h, (col + 1) * card_w, (row + 1) * card_h))
cropped.save(crop_path)
print(f"Sheet {W}x{H}, cell {idx}: col={col} row={row}, crop {card_w}x{card_h}, crop_path={crop_path}")
```

Then use the Read tool on the `crop_path` printed above to view the cropped card image and proceed to extraction.

**Important:** The cropped image is typically ~400×560 px — fully legible. Read all text fields directly from the image. Do not claim the resolution is too low or ask the user to type out text that is visible in the image. Only ask for clarification when something is genuinely ambiguous (e.g. a partially obscured icon, a word cut off at the edge).

Most path cards are single-sided. If the user mentions a back face, ask for its `imagesrc` + `image_rect` too.

## Step 2 — Pre-flight checks
Before extracting, identify these from the image and verify they exist in the data files. If anything is missing, **stop and ask the user how to register it** before proceeding:

- **Set**: bottom label shows the set name (e.g. "ANCIENT RUINS"). The corresponding entry must exist in `sets.json` with an `id` like `ancient_ruins`. New path sets are usually `type_id: "terrain"`, `size` = total physical cards in that set.
- **Token**: if the card has a "Powered [N]" header or any "[token]" icon in the text, the matching entry must exist in `tokens.json`.

## Step 3 — Extract metadata

### Visual zones on a path card
- **Top-left corner**: orange spawn arrow.
  - Downward triangle → `area_id: "within_reach"`
  - Upward triangle → `area_id: "along_the_way"`
- **Top-right area**: large purple gem with a number → `presence` (integer).
  - A book icon with a number alongside → top-level `guide_entry` (integer). Present only on path cards that reference the campaign guide.
- **Title block**: card name (`name`) and beneath it the type line.
- **Type line**: format is `Type — Trait / Trait / Trait` (e.g. "Being — Predator / Reptile").
  - First segment (lowercased) → `type_id`. For path cards this is almost always `"being"` or `"feature"`. Verify it exists in `types.json`.
  - Remaining segments joined with ` / ` → `traits` (preserve original casing).
  - **Never** include the `type_id` word in `traits`.
  - If "Pivotal" appears anywhere in the type line, add `"pivotal": true` and keep "Pivotal" in `traits`.
- **Powered header** (under the title, if present): "Powered [N]" → set `token_id` to the token shown (e.g. `"power"`) and `token_count` to the number as a **string** (`"1"`, `"3"`, `"0"`).
- **Body text**: see "Text formatting" below → `text`.
- **Challenge bands** (colored stripes near the bottom): each band corresponds to one challenge field.
  - Yellow sun band → `sun_challenge`
  - Blue mountain band → `mountain_challenge`
  - Red/crimson crest band → `crest_challenge`
  - Omit any band that's absent. The triggering icon itself is not duplicated in the text (the field name encodes which band it is).
- **Bottom-left stat badges** (read whatever is shown; omit entirely if absent — do **not** include zero defaults):
  - Red shield with sword → `harm` (string, may have `[per_ranger]` suffix, e.g. `"3"`, `"2[per_ranger]"`).
  - Green/cyan flag → `progress` (string, same suffix rules; `"3R"` printed on card → `"3[per_ranger]"`).
- **Bottom label**: pack code, set name, and set position like `"5 OF 12"` → `set_position` is the leading number as a string (`"5"`).

### Identical card grouping
If multiple physical printings share the same name, text, and stats but different set indices (e.g. "1 OF 12" and "2 OF 12"), model them as **one entry**:
- `quantity` = total number of physical copies.
- `set_position` = range string (`"1-2"`) or comma list (`"1, 5"`).
- `position` and `id` are based on the **starting** set index.

Ask the user how many physical copies exist if it's not obvious from the images.

### Text formatting (`text`, and the same rules for the three challenge fields)

Icon replacements:
- Stat icons: `[AWA]`, `[FIT]`, `[SPI]`, `[FOC]`
- Approach icons — read the shape carefully at small sizes before mapping:
  - `[conflict]` — two black shapes arranged in a circle separated by a mirrored-S gap, like a yin-yang symbol or two koi fish swimming in opposite directions.
  - `[exploration]` — a black circle with a vertical rhomboid needle inside, like a compass face (similar to the NATO logo but with only the vertical element, no cross).
  - `[connection]` — a plain black heart.
  - `[reason]` — an equilateral triangle pointing upward with stylized 3D edges drawn inside it, resembling an impossible geometric solid.
- Game tokens used inline: `[progress]`, `[harm]`, `[ranger]`, `[right_arrow]` (for the `>>` symbol), `[guide]` (the book icon used for guide-entry references like `[guide] 124`)
  - `[progress]` inline — an upside-down V / tent shape, with a small hollow triangle cutout at its base representing the tent entrance.
  - `[harm]` inline — a spiky star shape formed by two overlapping equilateral triangles (one flipped), like the Star of David, with a hollow triangular cutout in the center.
- Per-ranger suffix: `[per_ranger]` (the small ranger silhouette next to a number)
- For any other depicted token, use `[<token_id>]` matching `tokens.json`

Structure:
- Section breaks (the horizontal rule between rules-text blocks) → `<hr>`. Never use `\n\n`.
- A literal newline within a single block → `\n`.
- Italic flavor text → wrap in `<f>...</f>`.
- Bold ability test headers → wrap in `<b>...</b>`. The bold span covers the full test header: `[ASPECT] + [approach]` plus any parenthetical cost plus `: Verb` plus the optional `[difficulty]`. The descriptive "to …" tail that follows is in `<f>...</f>`, then the actual mechanical effect is plain. Worked examples:
  - `<b>[SPI] + [conflict]: Venture</b> <f>into the rift to</f> move your [ranger] to this feature.`
  - `<b>[FOC] + [conflict] (use 1 power): Stimulate</b> <f>the heart to</f> discard 1 challenge card attached to The Heart.`
  - `<b>[AWA] + [reason]: Investigate [2]</b> <f>archaeological wonders with Silaro to</f> add [progress] to a ruin or machine equal to your effort.`
- Standalone bold keywords like `Clear [harm]:`, `Response:`, `Enters Play:`, `Powered [1]:` → wrap in `<b>...</b>`.

Within a challenge field, a leading italicized phrase (the dramatic description) is wrapped in `<f>...</f>` before the mechanical effect. Example:
- `crest_challenge: "If you have 1 or more fatigue, <f>the archelon snaps at you.</f> [right_arrow] Suffer 1 injury."`

## Step 4 — Position and ID (estimated)
Read the target pack JSON and find the highest existing `position` (typically the last entry):
- `next_pos = last.position + last.quantity` (path cards always use `quantity`; `+1` only applies to ranger cards, which are out of scope here)
- `id = f"{pack_prefix}{next_pos:03d}"` (e.g. loa, position 315 → `"02315"`)

Confirm the resulting `name` does not already exist in the pack file.

**Note:** This position is an estimate for the proposal. Because multiple agents may run in parallel, the actual position is recalculated at write time (Step 6) from the live file state.

## Step 5 — Propose JSON and iterate

Field order convention (match neighboring entries in the pack file):
```
name, id, position, quantity, pack_id, category_id, type_id, area_id,
token_id, token_count, set_id, set_position, traits,
text, harm, progress, presence,
sun_challenge, mountain_challenge, crest_challenge,
guide_entry, image_rect, imagesrc
```

Always include: `name`, `id`, `position`, `quantity`, `pack_id`, `category_id: "path"`, `type_id`, `area_id`, `set_id`, `set_position`, `presence`.

Conditionally include: everything else only when it's actually on the card. Omit zero-valued or absent stats entirely.

`image_rect` and `imagesrc` were captured in Step 1 — include them in the entry. If for some reason they weren't provided yet, leave them out and note they can be added later.

Present the proposal in two forms:
1. A markdown table with one row per field (Field | Value) — this is the primary reading format the user prefers.
2. The full JSON entry below the table.

Explicitly call out any field that was unclear in the scan or that you guessed. Repeat the proposal until the user explicitly approves it. **Do not write to disk yet.**

## Step 6 — Write and commit
Once approved, **re-read the pack JSON immediately before writing** to get the current last position — another agent may have written since Step 4. Recompute `position` and `id` from the live file state, then append the entry. Use Python with `indent=2, ensure_ascii=False` to preserve smart quotes and special characters.

If the recomputed `id` differs from the one shown in the proposal, note the change to the user.

Then ask: "Commit? Push too?" — act on the answer.

Commit message format: `Add path card <Name> (<id>)`. For multiple cards added in one session: `Add path cards <Name1> (<id1>), <Name2> (<id2>), ...`. Do not include co-author trailers.
