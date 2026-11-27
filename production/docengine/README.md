# docengine — the upgraded documentary editing pipeline

Shared modules used by every Kaz-engine project (`production/<project>/`). They sit around the existing
board renderer (which is kept: it works) and replace its weakest parts.

## What was wrong (audit of the v1 pipeline, Pompeii)

| Area | v1 behaviour | Problem |
|---|---|---|
| Visual accuracy | images chosen by hand, checked only by eye on stills sheets | no systematic check; errors (4:15 in Harem v6) slipped through |
| Photo motion | move chosen by `sentence_index % 4` | content-blind, repetitive Ken Burns; could pan away from the subject |
| Transitions | one zoom-blur for every cutaway | monotonous; back-to-back shots hard-cut |
| Grade | one duotone for every image | gold looked brown, colour paintings flattened |
| Music | tracks tiled with hard loop seams, mono | audible jumps; mono mix |
| Mix | sidechain compressor on the whole bed, loudnorm, then re-encode | **true peak +1.6 dBTP in the delivered file** (clipping); bed in pauses only 0.6 dB under speech |
| Captions | long lines (199 > 42 chars), cues up to 0.33 s off the voice | hard to read |
| QC | manual stills review only | no checks for loudness, sync, spelling, freezes, duplicates, resolution |

## Modules

| Module | Role |
|---|---|
| `semantic.py` | CLIP ViT-B/16 (ONNX, CPU) text/image embeddings with an on-disk cache |
| `catalog.py` | historical eligibility: ancient objects must fit the era window + cultures; documents (photos, prints, paintings, maps) must name a project place; bans; metadata relevance |
| `audit.py` | **narration-to-visual audit**: for every sentence, works out what is actually on screen (camera focus on the board, cutaway, film insert, title card, 3D splice) and scores it. Flags `MISMATCH`/`WEAK` (pixels vs. sentence, relative to the whole script and to the eligible pool, with a concept check for borderline cases), `LABEL` (caption does not describe the image shown), `ENTITY` (narration names a place/thing the image doesn't show), `ERA`, `TEXT-UNRELATED`, `STALE` (same focus > 14 s), `REPEAT`. Suggests eligible alternatives. `--frames` also scores the rendered video. Exit 1 on `MISMATCH` → the render is blocked. Documented exceptions: `ok="reason"` on a directive. |
| `textmatch.py` | lexical relevance for text graphics, with number normalisation ("seventeen" = "17") and fuzzy stems |
| `motion.py` | content-aware camera for stills: YuNet face detection, spectral-residual saliency, Depth-Anything depth → `push_face`, `push_focus` (objects fill ~60% of frame), `pull_reveal`, `pan`/`tilt` ending on the subject, `parallax` (2.5D depth dolly). Mood sets speed; never repeats the previous move. Adaptive grade (exposure normalisation, colour kept for colour sources, warm monochrome for prints, light sharpening). Mount trimming. |
| `transitions.py` | context transitions: cut / dissolve / zoomblur / whip / dip, chosen per cut from the shot type and chapter mood, never the same twice running; shot-to-shot transitions without passing through the board |
| `mix.py` | stereo score (loops joined at quiet points with equal-power crossfades, chapter crossfades, `@hush` dramatic silences), look-ahead voice ducking from the narration envelope, widened ambience, panned SFX, two-pass linear loudnorm to −14 LUFS / −1.5 dBTP muxed once |
| `captions.py` | captions from word timestamps with script spelling; ≤ 2 × 42 chars, ≤ 6 s, ≤ 20 cps, comma-aware breaks, no orphans |
| `qc_auto.py` | technical QC of the rendered file: decode errors, black, freezes, static stretches, cut strobing, look consistency, loudness/true peak, bed-vs-speech balance, caption sync/reading speed/line length, on-screen spelling, image resolution vs display size, near-duplicates |

## Engine additions (project `kaz_engine.py` / `cutaways.py`)

* `@route <map> a,b,c "LABEL" dur=3` — animated route (Catmull-Rom path, dashed, arrowhead, label) through named map points (sea waypoints allowed)
* `@hush SECONDS` — music drops out for a dramatic beat and returns gently
* `@photo id crop=x0,y0,x1,y1 move=push_face` — manual crop / move override
* `ok="reason"` on `@card/@photo/@trip` — a documented, reviewed exception for the audit

## Project config (`project.json`)

`era` (from/to/cultures), `places`, `entities` (name → visual prompt), `banned_words`, `lexicon`, `moods` (per chapter),
`pool` (topic prefixes), `splices` (3D/footage inserted after render), `video`.

## Workflow

1. Script with directives → `narrate_kaz.py` (cached TTS) → `build/timeline.json`
2. `python3 ../docengine/audit.py` — fix every MISMATCH/WEAK/LABEL/ENTITY/ERA/STALE or document an `ok=` exception
3. Stills of every cutaway/transition/route → review
4. `finish_v2.sh` — render, sound, stereo mix, delivery encode, `qc_auto.py`, `audit.py --frames`
5. Captions: `captions.py`

Models (not in git, `production/models/`): `Xenova/clip-vit-base-patch16`, `Xenova/depth-anything-small-hf`,
`opencv/face_detection_yunet` (all from Hugging Face, ONNX).
