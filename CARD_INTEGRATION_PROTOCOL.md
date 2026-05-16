# Card Data Extraction & Integration Protocol

This document outlines the procedure for extracting metadata from card images and integrating them into the Earthborne Rangers JSON database.

## 1. Core Workflow
1.  **Image Input**: User provides a high-resolution scan of a card.
2.  **Extraction & Interpretation**:
    *   Identify key text (Name, Category/Traits, Text, Flavor).
    *   Interpret visual symbols (Icons, Directional arrows, Challenge types).
    *   Map metadata to existing schema values (Pack ID, Set ID, Position, Illustrator).
3.  **Drafting JSON**: Present a structured JSON object following `schema.ts`.
4.  **Verification Loop**: User corrects errors in text, identifiers, or mechanics.
5.  **Finalization**: User provides missing technical data (`imagesrc`, `image_rect`) and quantity.
6.  **Integration**: Once approved, the card is integrated into the relevant `.json` pack file following standard indexing rules (auto-incrementing position).

## 2. Card Anatomy & Visual Mapping

### Metadata Extraction
*   **Top Left**: An orange/amber triangle indicates spawn location:
    *   Downward pointing: `area_id: "within_reach"`
    *   Up(ward) pointing: `area_id: "along_the_way"`
*   **Top Right (Book Icon)**: The number following the icon is the `guide_entry`.
*   **Top Right (Number)**: Represents the card's **presence** (not cost). For path cards, this is typically `0`.
*   **Bottom Label**: Contains the `pack_id` (e.g., `LOA`), the `set_id` (e.g., `GENERAL`), and the `set_position` (e.g., `20/28`).

### Text & Content Rules
*   **Subtitle/Header**: The first word is the `type_id`. Any subsequent words separated by `/` are `traits`. For path cards, the `category_id` should always be set to `"path"`.
*   **Type ID**: The `type_id` should be set to the first word in the card subtitle (e.g., "attachment").
*   **Attributes**: Attribute names must be enclosed in brackets, e.g., `[SPI]`, `[AWA]`. If `harm`, `progress`, or any `approach` values are 0, do not include them in the JSON object.
*   **Icons & Symbols**:
    *   The triangle symbol in text maps to `[reason]`.
    *   The ">>" symbol maps to `[right_arrow]`.
*   **Mechanic Pattern (Bold/Flavor)**: 
    *   Patterns following `[Attribute] + [Reason]: Verb [Number]` must be wrapped in `<b></b>` tags.
        *   Attributes: `AWA`, `SPI`, `FIT`, `FOC`.
        *   Reasons: `reason`, `connection`, `exploration`, `conflict`.
    *   Text following this pattern that serves as flavor/context (often ending with "to") should be wrapped in `<f></f>` tags.
    *   Example: `<b>[SPI] + [reason]: Reflect [2]</b> <f>on the heart's trauma to</f> attach this emotion to a different organ.`
*   **Challenge Activations (Colored Backgrounds)**: Text on colored backgrounds must be extracted into specific challenge fields:
    *   Yellow background: `sun_challenge` field.
    *   Red/Crimson background: `crest_challenge` field.
    *   Blue background: `mountain_challenge` field.
*   **Formatting**: Use `<hr>` for horizontal lines separating text blocks instead of `\n\n`.

### Card Properties & Logic
*   **Quantity**: User must explicitly provide the number of physical copies.
*   **Deck Limit**: Only include `deck_limit` if `category_id == "ranger"`. Omit it otherwise.
*   **ID Generation**: Use pack-specific prefix (e.g., `02` for `loa`) + auto-incremented position based on the next available slot in the repo.
*   **Image Assets**: Each entry requires an `imagesrc` (URL to sprite) and `image_rect` (array of `[x, y, width, height]`).

## 3. Reference Schema (`schema.ts`)
Always validate extracted fields against the `TABLES.card` definition in `schema.ts`.
