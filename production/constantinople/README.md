# The Last Day of Rome: The Fall of Constantinople, 1453

The first film in the new cinematic style: photoreal AI reconstructions, real camera movement, a professional narrator and a full sound design. It replaces the museum-stills look of the earlier films.

## Status
| Step | State |
|---|---|
| 1. Topic analysis and research | Done: `research.md` (sources, claim register, accuracy rules) |
| 2. Structure | Done: 16 chapters (below) |
| 3. Narration script | Done: `script/*.md`, about 7,250 words |
| 4. Scene breakdown | Done: 312 shots written into the script under each paragraph |
| 5. Visual direction per shot | Done: `shots.json` / `SHOTLIST.md` (composed image and motion prompts) |
| 6. Visual identity | Done: `bible.json` + `visual_bible.md` (characters, locations, grades, rules) |
| 7. Narration timing | Done: Kokoro, timed per sentence |
| 8. Generate visuals | Done: 121 Z Image reconstructions (19.20 credits total), Wikimedia Commons photos and art, original maps and cards |
| 9. Final narration | Done: Kokoro `bm_lewis` (free, local) |
| 10. Edit, music, sound design, grade | Done: `tools/edit.py` (depth-parallax camera moves, grades, grain), Kevin MacLeod music (CC BY 4.0), synthesized SFX, -14 LUFS |
| 11. Review and delivery package | Done: 53:25 film, 1080p30. Package in `delivery/the_last_day_of_rome/`. The video file is not in git (7 GB master, rebuild with `tools/edit.py`) |

## Structure
| Act | Chapters | What it does |
|---|---|---|
| Introduction | 00 Cold open | The night of 28 May: last service in Hagia Sophia, the silent army, the title |
| The beginning | 1 Queen of Cities, 2 Emperor and Sultan | Geography, a thousand years of walls, the shrunken empire, the two rulers |
| The development | 3 Throat-Cutter, 4 A Divided City | Rumeli Hisarı, Rizzo, Orban's gun; church union, Giustiniani, the secret census, the chain |
| The turning point | 5 Guns of April, 6 First Weeks, 7 Four Ships, 8 Ships Over the Hill, 9 War Underground | The siege from first bombardment to the tunnels; the overland ships are the midpoint twist |
| The main event | 10 Signs and Omens, 11 The Last Night, 12 The Fall | Eclipse and omens, the last service, the three waves, Giustiniani's wound, the Kerkoporta question, the emperor's disappearance |
| The aftermath | 13 The Conqueror's City, 14 The Witnesses | The sack, Hagia Sophia, the new capital; how we know any of it |
| Conclusion | 15 The Last Day of Rome | Myths corrected, why 1453 matters, the walls today |

Open questions planted early and answered later: why the walls fell (Ch 5, 12), who Mehmed was (Ch 2, 13), what happened to Constantine (asked in the cold open, answered as honestly as the sources allow in Ch 12).

## Running time
The narration alone times at about 48 minutes with the free scratch voice. With the planned breathing room (music-only establishing passages, chapter cards, silences before the big moments, about 15% of runtime) the cut lands at about **55–57 minutes**. That's inside the 55–70 target without padding the script.

## Production pipeline
1. **Reference sheets.** One sheet per character and location in `bible.json` (20 in total), generated first and approved before anything else, so faces, armour, walls and Hagia Sophia stay consistent.
2. **Keyframes.** One photoreal still per shot from `shots.json` `image_prompt`, with the matching reference sheets attached as image references.
3. **Motion.** Approved keyframes are animated with Kling 3.0 Pro image-to-video (5 s, silent, 1080p) using `motion_prompt`. A 5 s clip can be eased to about 6 s. Longer shots get a cutaway still.
4. **Local finishing (free).** Maps, title cards, kinetic type, parallax on stills, grade, film grain and transitions in ffmpeg/Python, extending the existing `production/tools` pipeline.
5. **Sound.** Final narration with a free local voice (Kokoro; paid voices only with your OK). Sound effects from the Epidemic Sound library via Higgsfield. Licensed orchestral music. Mix at -14 LUFS with the music ducked under the voice.

## Budget
Higgsfield credit quotes as of today: still 0.75, Kling 3.0 Pro 5 s silent 8.75, Kling 3.0 Std 5 s 7.5.

| Tier | AI video clips | Estimated credits |
|---|---|---|
| A: every motion shot as video | 278 | ~3,600 |
| B: hero video, rest animated stills | 150 | ~2,200 |
| C: key moments only | 80 | ~1,450 |

The estimates include the reference sheets and a 25% retake allowance. My recommendation is **Tier B**: video where motion carries the story (battles, ships, crowds, the camera moving through spaces), and carefully animated stills for portraits, objects and quiet moments. See `SHOTLIST.md` for which tier each shot belongs to.

**Nothing paid is ever run without your explicit OK.**

## Files
- `script/` narration, with the shot lines (`> SIZE | MOVE | KIND | GRADE | @refs | description`) under each paragraph
- `bible.json` style prefix/suffix, negative prompt, grades, character and location descriptions, cost table
- `shots.json`, `SHOTLIST.md` generated by `tools/shotlist.py`
- `research.md` sources and fact check
- `tools/script_parse.py`, `tools/shotlist.py`, `tools/narrate_local.py`

## Known limitations
- Runtime is 53:25, a little under the 55-minute target. It was not padded.
- Some AI reconstructions keep small anachronisms: carrack/galleon-style ships in chapter 6, wheeled gun carriages, and a mitre-like hat on Notaras.
- Three Commons images could not be downloaded (rate limits), so those shots reuse another image from the same paragraph.
