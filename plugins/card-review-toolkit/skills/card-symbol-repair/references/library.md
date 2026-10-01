# Icon library

The supplied archive contains 175 transparent PNG candidates: mainly named set marks, plus energy/rarity/regulation/edition marks and some logos. All start unclassified and unverified. Resolution varies widely; a large canvas can contain a small or previously enlarged drawing. The assets were supplied by the user; their filenames do not establish official provenance.

`icon-catalog.json` records immutable file identity (`id`, `path`, `sha256`), dimensions, nonzero alpha bounds, alpha range, and review metadata (`category`, `status`, `variant`, `evidence`). Status is `unverified`, `verified`, or `rejected`. Verification must cite an inspected reference and exact variant; rejection should explain the unsuitable use, rather than imply the icon is wrong for every card. Preserve candidate PNG bytes; put transformations in task outputs. Change shared review metadata only when maintaining the library is within the request; otherwise save evidence in the task manifest.

Evidence should identify reference file/hash, collector ID, symbol location and crop, date, visual observations, and the applicable set/era/finish/language or printing variant when known. Unreadable source details stay unresolved. A verified record remains conditional on its documented variant, and must still be compared to the current card.

Examples: `HeartGold SoulSilver.png` is a candidate for comparison, not proof that it fits Ledyba 71/123. A Dragon Frontiers wordmark is not interchangeable with the small printed set mark. White disks and strokes can be opaque asset content despite transparency around them. Ambiguously named files such as `Layer 3 copy.png` require visual identification before use.

Dependencies for search: Python standard library. Repair and locality check: Pillow and NumPy; OpenCV optional. No API key is needed for the bundled library or deterministic compositing.
