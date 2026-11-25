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
