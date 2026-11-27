# Documentary QC rules (permanent, every film)

Accuracy comes before aesthetics. A scene that fails any check below is fixed or removed before delivery.
Each rule exists because a mistake happened. The tools enforce the rules; the eye checks are still done by hand.

## Workflow (do not skip steps)
1. **Narration first.** Write and time the narration. Every shot line sits under the sentence it illustrates.
2. **Exact subject per shot.** The shot line names the subject, place, period and grade. A general topic is not a subject.
3. **Verify every image by looking at it.** Do not trust the filename, the folder or the generation prompt.
   - Record the result in `review.json`: `VERIFIED`, `UNCERTAIN` or `REJECTED`, with a note.
   - Only `VERIFIED` images can reach the timeline. `edit.py plan` drops everything else and lists it in `build/skipped.json`.
4. **Mark the subject.** Every verified image gets a `focus` point (and an optional `focus2`) marked on a grid sheet (`tools/gridsheet.py`).
   - All zooms, pans, detail framings and crops are computed around that point.
   - There are no automatic "interest" guesses and no generic centre zooms.
5. **Register every word on screen.** Quotes, attributions, numbers, dates, labels, map names, split labels and lower thirds go in `text_register.json`, each with its source.
   - `qc.py` fails any text that is not in the register.
   - A quote that is also spoken must match the narration word for word, or be marked as reviewed indirect speech.
6. **Run `tools/qc.py`.** It writes `QC_REPORT.md`, a scene-by-scene table with an image / zoom / text / sync status for every shot.
   - Nothing is delivered while it reports failures.
7. **Render, then inspect the render.** Run `tools/aisheet.py` and look at every AI image at full size. Extract a frame from the middle of every shot and the end of every transition, and look at all of them on sheets.
   - Check maps for geography, text for spelling and overlap, and zooms for subject framing.
   - Run blackdetect and loudness (`qc.py --render`).
8. **Review the whole film again** before export. Fix in place; do not redesign scenes that pass.

## Image rules
- The image must show the subject being spoken about, in the right place and period.
  - Africa is not Athens. A Punic city is not a Greek acropolis or a whitewashed Aegean island.
  - Third-century BC Rome had no medieval round towers.
  - Ancient galleys had rams and oar banks; they were not Viking longships.
- Reject an image when any of these appear:
  - AI-generated writing or gibberish lettering.
  - Anachronisms: domes, minarets, pointed arches, medieval crenellated castles, paper books, feather quills, modern piers, roads, trousers or buildings.
  - The wrong people for the claim.
- Cropping a small flaw out is allowed. Record the crop in `review.json` and check the cropped frame.
- Use a real photograph or artwork only when its title and its content both confirm the subject. If the location cannot be confirmed, reject it.
- AI reconstructions are artistic interpretations. Never present them as photographs or archival records, and say so in the description.
- If no verified image exists for a sentence, use an accurate neutral visual (a map, a diagram, a text-free texture), not a borrowed or approximate picture.
- No image is reused outside deliberate detail beats.
- A photo of a modern reconstruction (a replica ship) or of a site as it is today (a medieval castle on an ancient hill) carries a lower third that says so, e.g. "a modern reconstruction" or "today".
- A split-screen label must describe what its picture actually shows (a stele is not an urn).
- After the render, re-check every AI image at about 1000 px or larger (four per sheet at 1400 × 788 each), not as thumbnails or 640 px frames: the 640 px pass on *The Fall of Carthage* missed 38 more faults. Look at the background, the wrists, the feet and every hand-held object as closely as the subject. Reject on sight:
  - wristwatches (check every bare wrist), stirrups, denim trousers, modern cups and mugs, food wrappers, chef's knives, modern anvils
  - Viking-style dragon-prow longships and rope-ladder shrouds, cast-iron bollards, drain grates, pop-up gazebo canopies
  - pointed or horseshoe arches, agave and other New World plants, Renaissance or modern buildings behind a "period" street
  - satellite dishes, air-conditioning units, power lines and utility poles, electric light in windows
  - electric cables, wall lamps, street lamps, metal railings, glass lanterns, glass bottles
  - sunglasses, metal-nib pens, printed paper or maps with fake lettering, patio umbrellas
  - domes, church bell towers, medieval round towers and castle walls, great helms, valved brass trumpets
  - apartment blocks, marinas with white motorboats, concrete buildings, modern field patterns behind a "period" scene
  - AI images made to look like a real excavation or archive photograph

## Zoom and crop rules
- The subject stays in frame for the whole move. Pans and tracks travel toward the subject, never away from it.
- Detail beats are framings centred on the marked subject (or `focus2`), at no more than about 1.6× enlargement.
- Low-resolution sources (under about 900 px across the used area) get no detail beats.
- Never crop out faces, the main object or key architecture. Never stretch or distort.

## Text rules
- Never invent a quotation. Use a published translation of the ancient text, mark it "(translated)" and cite book and chapter.
- Paraphrase is narration, not a quote card.
- Dates and numbers come from the claim register in `research.md`. Approximate dates carry "c.", and timelines are in chronological order.
- Map labels are checked against coordinates. Distances are computed, not guessed.
- Every map is inspected on a check sheet (`build/gfxcheck`, last frame) at full size. Look for:
  - labels hidden by routes, pulses or the camera zoom
  - a city label with no dot
  - shading that misses land it should cover (Picenum, Sardinia), or that covers places it should not (all the Balearics, Spain before the Barcids)
- Territory polygons run out into the sea so that the land mask draws the coast. Inland borders are softened and the map says "borders approximate".
- No decorative text. If a piece of text cannot be verified, leave it out.

## Technical rules
- Script edits must not shift shot ids silently. `shotlist.py` refuses until assets and `review.json` are renamed.
- No gaps between shots, no black stretches outside intended dips, loudness about -14 LUFS with true peak under -1 dB.
- Keep a backup of anything replaced (`build/gen_rejected`, `build/clips_rejected`).
- Credit only the photos that are actually on screen. `package.py` reads them from the timeline.
- No still holds longer than about 8 s. When a graphic outlasts its animation, the tail is split into several reframings of the last picture, each kept above 900 source pixels across.
- `qc.py` also compares file contents, so one picture saved under two names counts as a reuse.
