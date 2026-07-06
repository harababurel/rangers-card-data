# Earthborne Rangers Card Data

This repository contains structured JSON card data for Earthborne Rangers.

## Card Schema Notes

Card fields are declared in `schema.ts`. Card entries live under `packs/`.

### Approach Icons

Cards may expose approach icons in two complementary ways:

- `approach_conflict`, `approach_reason`, `approach_exploration`, and `approach_connection` are numeric count fields. These remain the backward-compatible way to ask how many icons of each approach a card has.
- `approach_icons` is an optional ordered array of approach ids. When present, it records the printed left-to-right icon order from the card image.

Valid `approach_icons` values are:

- `conflict`
- `reason`
- `exploration`
- `connection`

Example:

```json
{
  "approach_reason": 1,
  "approach_exploration": 1,
  "approach_icons": ["reason", "exploration"]
}
```

Clients that render cards should prefer `approach_icons` when it is present. Clients that filter, search, or calculate icon totals can continue using the numeric `approach_*` fields. If `approach_icons` is absent, clients may derive a fallback order from their own default display order, but that fallback should not be treated as the printed card order.

When adding or editing data, keep `approach_icons` consistent with the numeric count fields. Duplicate icons are represented by repeated array values, for example `["conflict", "conflict", "exploration"]`.

## License

- **Code** (the curator tool, scripts, and schema) is licensed under the [MIT License](LICENSE).
- **Card data** (the JSON files and translations) is released under [CC0 1.0](LICENSE-DATA) (public domain dedication).

This is an unofficial, fan-made database. *Earthborne Rangers*, its card text, and its artwork are © Earthborne Games. This project is not affiliated with or endorsed by Earthborne Games.
