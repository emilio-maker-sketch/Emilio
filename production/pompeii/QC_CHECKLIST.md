# Pre-delivery QC (mandatory, every video)

Learned from Harem Conspiracy v6, 4:10–4:30: a triptych of museum objects rendered with two near-blank
panels and cropped objects, then a single kohl tube sat on the board while the narration described the
harem as an institution (wives, children, officials). Spot-checking ~11 frames missed it.

## 1. Dense review against the script
`python3 qc_sheets.py final.mp4 captions.srt qc/` gives one sheet per minute, one frame every 2 s,
with the spoken line printed under every frame. Read **every** sheet, every cell:
- Does the picture show what the words say at that moment? A generic "period object" under a
  specific claim (people, places, events) is a fail. Pick an image of the thing named, or use
  kinetic type / a map / a document card instead.
- No single image should hold the screen for more than ~6 s unless the narration is about that image.
- Every image is whole: no object cut off, no blank backdrop panels, no unreadable labels.

## 2. Image framing rules (enforced in cutaways.py)
- Mount/border trimming runs only on photographic prints (record `medium` contains "print" or
  "photograph"). Museum object photos keep their full frame; the gradient studio backdrop is not a border.
- Triptych panels use `frame_object()`: they crop around the object's edges at the panel's aspect ratio
  with a margin, never a blind center crop.
- `cutaways.audit()` must print no WARN lines before a full render.

## 3. Before rendering the full video
Render stills at every cutaway (`kaz_engine.py stills t1,t2,...`) and look at them as a contact sheet.

## 4. Added after the full v6 review (all fixed in v7)
- Object cutouts use rembg (IS-Net). GrabCut left white/grey blobs (studio base, shadows) under scarabs,
  the wand, the harp and the eye amulet. Check every file in build/cut on a dark board colour.
- Archival footage ranges must contain picture only: scrub each range and exclude the old film's own
  intertitles and flash frames. Dark shots are auto-stretched so they read (Theban cliffs).
- Every overlay text must be fully on screen, readable, for at least ~2 s (thesis cards were only fully
  typed for 0.2 s).
- The end card holds through the sign-off; never drop back to the board after the title.
- Footage must illustrate the sentence (no 1920s workers sifting pots under "the neck stayed wrapped").
- Run qc_sheets.py ONCE at a time (two runs share a temp frame and produce fake glitches).

## 5. Added for Pompeii (video 3)
- Cutaways (@foot/@photo/@object/@type/@trip) are written in script.md directly above the sentence they illustrate.
  No more hand-numbered sentence indices: a mismatch is visible when reading the script.
- Before any render: stills every 4 s, captioned with the spoken line (`stills_sheets.py`), read every cell.
- Archival footage of a later event (Vesuvius 1944) is labelled with its date on screen AND the narration says so.
- Museum paintings/frescoes/photos are never cut out like objects (make_card checks the medium).
- Wikimedia Commons rate-limits this machine; prefer The Met (CC0) and keep sources PD/CC0.
- Thumbnail text must not attach a specific claim to an image that does not show that specific thing.
