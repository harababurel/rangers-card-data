# `set_position` Field: Caveats for Consumers

## What `set_position` Represents

Each card's `set_position` field is intended to match the **number printed on the physical card** — e.g., a card printed as "REWARDS · 25/29" should have `set_position: "25"`.

This field is a free-form text string (it can represent a range such as `"1-2"` for cards with `quantity > 1`). It is not enforced as unique or numeric anywhere in this repository's schema.

---

## Known Caveat: `(set_id, set_position)` is NOT globally unique

Due to the game's expansion structure, the combination of `set_id + set_position` does **not** uniquely identify a card across the full dataset. Two different situations cause this:

### 1. Sets that span multiple packs (e.g., Rewards)

The `reward` set exists in both the Core set (`pack_id: "core"`) and Legacy of the Ancestors (`pack_id: "loa"`). Each pack's reward cards are numbered independently on the physical cards, starting from 1. This means both packs can contain a card with `set_id: "reward"` and `set_position: "25"`.

**Correct join key:** `(pack_id, set_id, set_position)` — not `(set_id, set_position)`.

### 2. Expansion sets that shuffle into a base set (e.g., The Valley)

Some sets like `the_valley` have a large base set in the Core pack (e.g., 14 cards, numbered 1–14) and smaller supplemental sets in expansion packs (e.g., Spire in Bloom adds 3 cards, also numbered 1–3, intended to be physically shuffled into the base Valley deck).

These expansion cards intentionally share `set_id: "the_valley"` and `set_position` values (1, 2, 3) with different cards in the Core pack. The `pack_id` is what distinguishes them.

**Correct join key:** again, `(pack_id, set_id, set_position)`.

---

## Historical Note

Prior to normalizing `set_position` to match printed card numbers, this repository used a globally-incrementing `set_position` within each `set_id` (e.g., LOA reward cards were numbered 27–55 rather than 1–29). That approach made `(set_id, set_position)` unique but did not reflect the physical cards. The current approach prioritizes physical accuracy.

---

## Summary

| Join key                          | Unique? | Matches physical card? |
|-----------------------------------|---------|------------------------|
| `set_id + set_position`           | No      | Yes                    |
| `pack_id + set_id + set_position` | Yes     | Yes                    |

Always use `pack_id` as part of any lookup or join involving `set_position`.
