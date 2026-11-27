# Editing pipeline upgrade — test report

Test documentary: **Pompeii** (18:16), re-edited and re-rendered with the upgraded pipeline (v2) and compared with the
version delivered before the upgrade (v1). Then a new documentary, **Nineveh** (13:23), was made entirely on the new pipeline.

## 1. What was wrong with v1 (found by inspection and by the new tools)

| Area | v1 | Evidence |
|---|---|---|
| Visual accuracy | images chosen by hand, checked only by eye | audit of v1: 2 mismatches (1:28 "ordinary people" over a lamp/bottle/ring; 2:01 temple photo while Vesuvius is discussed), 3 weak matches, a 19th-c. Egyptian-provenance bracelet labelled only "Roman" |
| Pacing | no measurement | 7 stretches where the same card held focus 15–23 s |
| Camera | move picked by `sentence_index % 4` | identical Ken Burns patterns regardless of content; pans could end away from the subject |
| Transitions | one zoom-blur everywhere; back-to-back shots hard-cut | |
| Grade | one duotone for all images | colour paintings turned brown-teal |
| Audio | mono; whole bed ducked by one compressor; loudnorm then re-encode | **true peak +1.6 dBTP (clipping)**; music in pauses only 0.7 dB under speech |
| Captions | 351 cues | **199 lines over 42 characters** |
| QC | stills sheets only | no automatic check of loudness, sync, spelling, freezes, duplicates, resolution |

## 2. What was built (`production/docengine/`)

* **Narration-to-visual audit** (`audit.py`): works out what is actually on screen through every sentence (camera focus on the
  board, cutaway, film insert, title, 3D splice) and checks it: CLIP image/sentence relevance judged against the whole script
  and the eligible pool, a concept check for borderline cases, museum-catalogue metadata for inscribed objects, caption-vs-image
  consistency, named places/things must be visible, historical eligibility (era window + culture; documents must be of the place),
  text cards (word/number overlap, paraphrase via the text encoder), long holds, repeats. Render is blocked on any mismatch;
  editorial exceptions must be written into the script with a reason and are listed in the report.
  *Validation*: 5 deliberately wrong images planted in Pompeii → **5/5 caught**, 0 false alarms on the corrected film.
* **Historical eligibility** (`catalog.py`): rejects off-era/off-culture objects and documents that are not of the subject
  (it removed e.g. "Rembrandt's son Titus" and a 19th-c. American portrait from the suggestions).
* **Content-aware camera** (`motion.py`): face detection (YuNet), saliency, monocular depth (Depth Anything) → push to face,
  push to subject (objects fill ~60% of frame), reveal, pans/tilts that end on the subject, 2.5D parallax; mood sets speed;
  never repeats the previous move. Mount/edge trimming, manual `crop=`/`move=` overrides.
* **Grade** (`motion.py`): exposure measured on the object (not the museum backdrop), colour kept for colour sources, warm
  monochrome for 19th-c. prints (from the museum medium), gentle curve, light sharpening.
* **Transitions** (`transitions.py`): cut / dissolve / zoom-blur / whip / dip chosen per cut from shot type + chapter mood,
  never the same twice running; shot-to-shot without passing through the board.
* **Maps**: animated routes (`@route`) through named points incl. sea waypoints; routes fade when their moment has passed.
* **Sound** (`mix.py`): stereo score with loop points at quiet bars and equal-power crossfades; `@hush` dramatic silences;
  look-ahead voice ducking that holds through short gaps and swells only at section breaks; widened ambience; two-pass
  linear loudnorm, audio encoded once.
* **Captions** (`captions.py`): from word timestamps, anchored to the exact synthesised sentence starts, ≤ 2×42 chars, ≤ 20 cps.
* **Technical QC** (`qc_auto.py`): decode errors, black, freezes, static stretches, cut strobing, look outliers (planned
  title/film/3D looks excluded), loudness/true peak, bed-vs-speech balance on exact sentence boundaries, caption sync against
  exact sentence starts, reading speed, line length, on-screen spelling (with project lexicon), image resolution vs display
  size, near-duplicate images.
* **Credits** (`credits.py`) generated from the images the film actually uses; **compare** (`compare.py`) for A/B renders.

## 3. Pompeii v1 → v2 (same narration)

| Check | v1 | v2 |
|---|---|---|
| Accuracy audit | 2 MISMATCH, 3 WEAK, 7 STALE, 1 mislabelled provenance | 0 (documented exceptions listed) |
| Loudness / true peak | −14.4 LUFS / **+1.6 dBTP (FAIL)** | −14.0 LUFS / −1.3 dBTP (PASS) |
| Music in pauses vs speech | 0.7 dB under (WARN) | 6.6 dB under (PASS) |
| Captions | 351 cues, 199 lines > 42 chars | 270 cues, 0 lines > 42 chars, starts on exact sentence starts |
| Spelling (on-screen) | 15 unknown | 0 |
| Audio | mono | stereo |
| Static stretches / freezes / black | 0 / 0 / 0 | 0 / 0 / 0 |

Visible changes (side-by-side stills in `production/pompeii/build/compare/`): 1:28 an empty dark frame in v1 → a watercolour of
a Pompeian house; Pliny's route animated on the map; umbrella pines in neutral monochrome instead of a sepia wash;
content-aware moves on every photograph; context transitions.

Found and fixed during the test: the v2 board render had started before the grade fix, so the gold coin in one triptych read
bronze → the 7 affected cutaways were re-rendered and overlaid frame-accurately.

## 4. Nineveh (new film, built on the pipeline)

* Pre-render audit: 0 mismatches, 0 weak, 0 stale after fixes; 7 documented exceptions (each with its reason).
* Technical QC: all PASS except one image the Met only provides at 800 px (upscaled 1.8× on the board).
* Stills review found a stale cached background label ("MEDIA") → frames where it is visible were re-rendered and overlaid.

## 5. Limits (honest)

* CLIP cannot read cuneiform or understand "DNA"; the audit compensates with museum metadata and documented exceptions,
  but abstract sentences still need an editor's judgement.
* Source images come from public-domain museum collections (Wikimedia Commons blocks this machine); some periods/events
  have no authentic imagery, which is why reconstructions (3D, silent-film scenes) are used and labelled.
* Rendering is CPU-only: a full 18-minute render takes ~1.5 h.
