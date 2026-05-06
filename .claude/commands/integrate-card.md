Integrate a card from images into the card database.

## Target pack
If `$ARGUMENTS` specifies a pack (e.g. "legacy" or "packs/legacy/legacy.json"), use that file. Otherwise default to `packs/core/core.json`. The pack prefix for IDs is the 2-digit zero-padded index of that pack in `packs.json`.

## Step 1 — Extract metadata from the images
Read the most recently pasted card images (front and back). Extract:

**From the front face:**
- `name`
- Type line: `category_id` (first segment, lowercased), `type_id` (for location cards always `"location"`; check `types.json` for others), `traits` (remaining segments joined with ` / `)
- `pivotal: true` if "Pivotal" appears in the type line (also keep it in `traits`)
- `set_position` (e.g. "2 OF 37" → `"2"`)
- `presence` (the purple icon value)
- `progress` (the cyan badge value; suffix `R` → `[per_ranger]`, e.g. `3R` → `"3[per_ranger]"`)
- `text` — card ability text with:
  - Stat icons: `[AWA]`, `[FIT]`, `[SPI]`, `[FOC]`
  - Approach icons: black heart → `[connection]`, compass/boot → `[exploration]`, sword/shield → `[conflict]`, book/lightbulb → `[reason]`
  - Other tokens: `[progress]`, `[harm]`, `[ranger]`, `[right_arrow]`, `[per_ranger]`
  - Italic flavor text wrapped in `<f>...</f>`
  - Bold keywords wrapped in `<b>...</b>`
  - Section breaks as `<hr>`

**From the back face:**
- `guide_entry` (the book icon number)
- `arrival_setup` (full text under "Arrival Setup", bold keywords as `<b>...</b>`, newlines as `\n`)
- `path_deck_assembly` (if a "Path Deck Assembly" section is present)

## Step 2 — Determine position and ID
Read the target pack JSON. Find the last card:
- `next_pos = last.position + (1 if last.category_id == "ranger" else last.quantity)`
- `id = f"{pack_prefix}{next_pos:03d}"`

Check that no card with this `name` already exists in the pack.

## Step 3 — Propose JSON
Show the full proposed card entry with `"image_rect": []` and `"imagesrc": ""` as placeholders (the curator will fill these in). Ask the user to confirm before writing anything.

## Step 4 — Write to pack file
After confirmation, append the card to the pack JSON and save with `indent=2, ensure_ascii=False`.

## Step 5 — Curator merge (if present)
Check for `packs/core/new_encounter_cards.json` (or the equivalent for the target pack). If it exists, diff it against the entry just written and report the differences. Ask the user if they want to apply the curator's version (typically just `image_rect` and `imagesrc`). After applying, delete the `new_encounter_cards.json` file.
