Parse a card from images and integrate it into the card database, step by step.

## Target pack
If `$ARGUMENTS` specifies a pack (e.g. "legacy" or "packs/legacy/legacy.json"), use that file. Otherwise default to `packs/core/core.json`. The pack prefix for IDs is the 2-digit zero-padded index of that pack in `packs.json`.

## Step 1 — Request images
Ask the user to provide card image(s): either paste screenshot(s) directly into the chat, or provide the path(s) to image file(s) on disk. Wait for their response before proceeding.

## Step 2 — Extract metadata
Read the provided image(s). Extract all of the following:

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

## Step 3 — Determine position and ID
Read the target pack JSON. Find the last card:
- `next_pos = last.position + (1 if last.category_id == "ranger" else last.quantity)`
- `id = f"{pack_prefix}{next_pos:03d}"`

Check that no card with this `name` already exists in the pack.

## Step 4 — Propose JSON and iterate
Show the full proposed card entry with `"image_rect": []` and `"imagesrc": ""` as placeholders. Explicitly call out any fields you could not read clearly or that are ambiguous, and ask the user to supply or confirm them. Repeat until the user explicitly approves the entry — do not write anything yet.

## Step 5 — Write to pack file
Append the confirmed card to the pack JSON and save with `indent=2, ensure_ascii=False`.

Then tell the user: "Written. Please match this card in the curator tool, fill in the image crop, and re-export. Let me know when you're done."

## Step 6 — Apply curator image data
Wait for the user to confirm they've re-exported. Then check for `new_encounter_cards.json` in the target pack directory. Diff it against the entry written in Step 5:
- Report any differences found.
- Warn the user if there are unexpected differences beyond `image_rect` and `imagesrc`.
- Apply `image_rect` and `imagesrc` from the curator export to the card in the pack JSON.
- Delete `new_encounter_cards.json`.

## Step 7 — Commit and push
Ask: "Commit? Push too?" and act on what they say.

When committing, the message format is: `Add <category> card <Name> (<id>)` (e.g. `Add location card The Philosopher's Garden (01437)`).
