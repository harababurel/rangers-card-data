# AI Context & Project Guide

## Project Overview
This repository is a fork of [zzorba/rangers-card-data](https://github.com/zzorba/rangers-card-data). It serves as a structured, machine-readable JSON database for the tabletop game **Earthborne Rangers**.

### Current State (Upstream)
The upstream repository primarily focuses on:
1. **Player/Ranger Cards:** Containing aspects, rewards, and core player cards.
2. **Game Terminology & Entities:** Defining tokens, areas, aspects, sets, and types.
3. **Internationalization (i18n):** A massive portion of the upstream history is dedicated to translating traits, flavor text, and card text into German, French, Italian, Russian, and Spanish.

### Fork Objectives (User's Goals)
The primary focus of this fork shifts away from pure localization and towards **data completeness and correctness for the English baseline**:

1. **Fix Typos and Errors:** Correct ongoing mistakes, errata, and typos present in the upstream English data.
2. **Complete the Database (Missing Cards):** The most critical goal is to add all non-player cards. The repository currently lacks data for:
   - Path cards
   - Location cards
   - Mission cards
   - Weather cards
   - Moment cards
   - Challenge cards
3. **Prioritize English:** While i18n is nice to have, it is a secondary concern. The main focus is structuring and validating the English text and data.

## Technical Context & Schema Notes

### File Structure
- `schema.ts`: Defines the data structures and relationships (Foreign Keys, text fields, etc.).
- Root JSON files (`areas.json`, `aspects.json`, `tokens.json`, `sets.json`, `types.json`): Contain the core enum-like data entities.
- `packs/`: Directory containing the actual card data, grouped by release/pack.
- `taboos/`: Directory for balance updates/errata restrictions.
- `i18n/`: Directory for localization files (currently secondary for this fork).

### Schema Insights
The existing `schema.ts` already shows foresight for encounter cards, even if the data isn't populated yet. 
- **Card Fields:** The `card` collection supports fields like `harm`, `progress`, `approach_conflict`, `approach_reason`, `approach_exploration`, `approach_connection`, and optional `approach_icons`.
- **Approach Icon Order:** The numeric `approach_*` fields store icon counts for compatibility and filtering. The optional `approach_icons` array stores the printed left-to-right order using `conflict`, `reason`, `exploration`, and `connection`. When present, it is the canonical rendering order and must match the numeric counts, including duplicate icons.
- **Encounter Specifics:** The schema explicitly supports `sun_challenge`, `mountain_challenge`, and `crest_challenge` as text fields, which are strictly required for generating Challenge, Path, and Location cards.
- **Formatting Conventions:** 
  - Standard italics are generally replaced by the `<f>` tag for flavor text (e.g., `<f>Flavor text here</f>`).
  - Game icons and attributes are typically enclosed in brackets (e.g., `[progress]`, `[FOC]`, `[FIT]`, `[SPI]`, `[AWA]`).

### Card ID Generation
A card's 5-digit `id` is a composite of the Pack ID and the card's position within that pack:
- **First 2 digits (Pack Prefix):** Determined by the `position` of the pack in `packs.json`, zero-padded (e.g., `01` for Core set, `02` for Legacy of the Ancestors).
- **Last 3 digits (Card Position):** Corresponds to the `position` value of the individual card within its JSON file, zero-padded (e.g., a card with position `47` gets `047`).
- **Example:** A card in the Core set (`01`) with position `47` gets the ID `"01047"`.
- **Upstream ID divergence (ITM):** Pack positions differ from upstream because this fork added MOP (`06`) and MIV (`07`). *Into the Maw* (`itm`) is position `8` here, so its cards are `08201-08205`; upstream uses `06201-06205`. When syncing ITM data or `i18n/*/packs/itm/itm.po` from upstream, remap `062xx` -> `082xx`.

### Functional Conventions
- **Hierarchical Classification:** Every card must have a `category_id` (representing the card back/deck context: `ranger`, `path`, `location`, `weather`, `mission`, `challenge`) and a `type_id` (representing the functional content: `being`, `gear`, `moment`, etc.).
- **Traits vs. Types:** Do NOT include the card's functional type in its `traits` field. For example, a card with `type_id: "being"` should not have "Being" in its `traits` string.
- **Area IDs:** Path cards use `area_id` to represent the spawn arrow. The valid values are `within_reach` (down arrow) and `along_the_way` (up arrow). Ranger cards typically use `in_play`.
- **Aspect Cards:** These cards use numeric fields (`awareness`, `spirit`, `fitness`, `focus`) to define base attribute values.
- **Challenge Cards:** These use `awa_value`, `spi_value`, etc., for the aspect modifiers, and `challenge_icon` for the band color icon.

### Identical Card Grouping
Many Path and Location cards are identical in text and stats but have different set indices (e.g., *Wading Ursus* 1/5 and 2/5). To keep the database clean:
- **Single Entry:** Use one JSON object per unique card template.
- **`quantity`**: Set this to the total number of physical copies (e.g., `2`).
- **`set_position`**: Use a string range or list (e.g., `"1-2"` or `"1, 5"`).
- **`position`**: Use the **starting position** of the range.
- **`id`**: Based on the starting position (e.g., `"01256"`).
- **Curator Logic**: The UI automatically accounts for `quantity` when suggesting the next available position.

### Double-Sided Card Modeling
Physical cards that are printed on both sides fall into three distinct patterns, each modeled differently:

#### Pattern 1: Location cards (inline back fields)
The back of a location card is structural metadata — never interacted with independently. Both faces are stored in a single card entry using two dedicated text fields:
- **`path_deck_assembly`** *(optional)*: Instructions for assembling the path deck for this location.
- **`arrival_setup`** *(mandatory)*: Instructions shown when rangers arrive at this location.
- The existing `guide_entry` field also lives on the location entry and refers to the back face.
- Location cards do **not** use `back_card_id`.

#### Pattern 2: Flip cards (same set position on both sides, both sides independently playable)
Both faces are distinct playable card states sharing one physical slot (e.g., *Prototype (Expanded)* / *Prototype (Contracted)*). Model as two separate card entries:
- **Front entry**: normal card with `back_card_id` pointing to the back entry's `id`. Carries `position`, `set_position`, and `quantity`.
- **Back entry**: its own card entry with `back_card_id` pointing to the front. Its `id` uses a `b` suffix (e.g., front `"02028"` → back `"02028b"`). **It must share the same `set_position` as the front entry so that rendering tools like earthborne.build display it correctly.** It does **not** have its own `position` or `quantity` since it is never independently dealt.

#### Pattern 3: Distinct-set-position double-sided cards (weather, missions, etc.)
Each face carries its own set position (e.g., a physical weather card has position 1 on the front and position 2 on the back). Treat each face as a fully independent card entry with no cross-referencing. The physical co-printing is a production detail, not a data relationship.

## Guidelines for Future AI Agents
When picking up tasks in this repository:
1. **Adding Encounter Cards:** Before adding new card types (e.g., Weather, Moments), verify that their corresponding IDs exist in `types.json` and the necessary campaign/day sets exist in `sets.json` or `subsets.json`.
2. **Updating Schema:** If adding a card property that doesn't exist in `schema.ts` (e.g., a specific "Travel" requirement for paths), ensure `schema.ts` is updated to reflect it.
3. **Ignore i18n Updates (Unless Prompted):** When adding new English cards or fixing typos, do not automatically attempt to generate or update translation `.po`/`.json` placeholders unless explicitly requested by the user. Focus purely on the primary JSON data structure.

## Custom Commands & Repo-Local Skills
This repository contains custom, repo-local skills/commands designed to automate complex tasks for AI agents:

- **Path Card Parser (`parse-card`)**:
  - **Claude version**: Defined in [`.claude/commands/parse-card.md`](.claude/commands/parse-card.md).
  - **Gemini/Jetski version**: Defined in [`.gemini/commands/parse-card.md`](.gemini/commands/parse-card.md).
  - **Usage**: If the user asks you to parse a path card from an image (providing `imagesrc` and `image_rect`), you **must** read and follow the instructions in the relevant version of the `parse-card.md` file. It outlines the exact visual zones, text formatting rules, and integration steps.

## Protocol: Encounter Card Integration
Newly exported cards usually reside in `packs/core/new_encounter_cards.json`. Follow this rigorous workflow for integration:

### 1. Pre-flight Checks
- **New Tokens:** If a card uses a `token_id` not in `tokens.json`, register it first.
- **New Sets:** If a card uses a `set_id` not in `sets.json`, register the set (Type: `terrain`, Size: based on physical cards).

### 2. Standard Indexing Logic
To maintain a continuous sequence in `core.json`, re-index all cards from the insertion point (usually the end):
- **Next Position (`pos`):** `last_card.position + last_card.physical_slots`.
- **Physical Slots:** 
    - Ranger Cards (`category_id: "ranger"`): Always 1 slot.
    - Encounter Cards (all other categories): `quantity` slots.
- **Card ID:** `pack_prefix` (2 digits) + `pos` (3 digits, zero-padded). Example: `01` + `353` = `01353`.

### 3. Automated Merge Script
Always use a Python snippet for the merge to ensure JSON validity and correct indexing:

```python
import json
with open("packs/core/core.json", "r") as f: core = json.load(f)
with open("packs/core/new_encounter_cards.json", "r") as f: new_cards = json.load(f)

# Find next position
last = core[-1]
current_pos = last["position"] + (1 if last["category_id"] == "ranger" else last["quantity"])

for card in new_cards:
    card["position"] = current_pos
    card["id"] = f"01{current_pos:03d}" # Adjust pack prefix if not EBR
    current_pos += (1 if card["category_id"] == "ranger" else card["quantity"])

core.extend(new_cards)
with open("packs/core/core.json", "w") as f:
    json.dump(core, f, indent=2, ensure_ascii=False)
```

### 4. Submission
- **Non-ASCII:** Always use `ensure_ascii=False` when saving JSON to preserve smart quotes and special characters.
- **Cleanup:** Delete `new_encounter_cards.json` after a successful merge.
- **Commit Message:** List all integrated card names and their final IDs.
