# AI Context & Project Guide

> **IMPORTANT:** This file must be kept in sync with `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` at all times.

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
- **Card Fields:** The `card` collection supports fields like `harm`, `progress`, `approach_conflict`, `approach_reason`, `approach_exploration`, `approach_connection`.
- **Encounter Specifics:** The schema explicitly supports `sun_challenge`, `mountain_challenge`, and `crest_challenge` as text fields, which are strictly required for generating Challenge, Path, and Location cards.
- **Formatting Conventions:** 
  - Standard italics are generally replaced by the `<f>` tag for flavor text (e.g., `<f>Flavor text here</f>`).
  - Game icons and attributes are typically enclosed in brackets (e.g., `[progress]`, `[FOC]`, `[FIT]`, `[SPI]`, `[AWA]`).

### Card ID Generation
A card's 5-digit `id` is a composite of the Pack ID and the card's position within that pack:
- **First 2 digits (Pack Prefix):** Determined by the `position` of the pack in `packs.json`, zero-padded (e.g., `01` for Core set, `02` for Legacy of the Ancestors).
- **Last 3 digits (Card Position):** Corresponds to the `position` value of the individual card within its JSON file, zero-padded (e.g., a card with position `47` gets `047`).
- **Example:** A card in the Core set (`01`) with position `47` gets the ID `"01047"`.

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

## Guidelines for Future AI Agents
When picking up tasks in this repository:
1. **Adding Encounter Cards:** Before adding new card types (e.g., Weather, Moments), verify that their corresponding IDs exist in `types.json` and the necessary campaign/day sets exist in `sets.json` or `subsets.json`.
2. **Updating Schema:** If adding a card property that doesn't exist in `schema.ts` (e.g., a specific "Travel" requirement for paths), ensure `schema.ts` is updated to reflect it.
3. **Ignore i18n Updates (Unless Prompted):** When adding new English cards or fixing typos, do not automatically attempt to generate or update translation `.po`/`.json` placeholders unless explicitly requested by the user. Focus purely on the primary JSON data structure.
