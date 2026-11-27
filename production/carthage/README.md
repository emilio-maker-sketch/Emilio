# Carthage Must Be Destroyed: The Fall of Rome's Greatest Rival

Third film. About 58–60 minutes, 1920×1080, 30 fps. Built to the "world-class cinematic documentary editing" brief.

## Budget
Higgsfield credits: 47.70 of the 50 allowed (see `credits_ledger.md`): 198 Z Image stills, 9 Seedance 2.0 Mini clips.
Everything else is free: Kokoro narration (voice bm_lewis), Wikimedia Commons photographs and paintings, Natural Earth maps,
synthesized sound effects, Kevin MacLeod music (CC BY 4.0).

## Pipeline
| Step | Tool |
|---|---|
| Script with per-sentence visual plan | `script/*.md` (shot kinds: vid, still, photo, detail, map, diagram, timeline, stat, split, quote, card) |
| Shot list and AI prompts | `tools/shotlist.py` |
| Narration | `tools/narrate_local.py` |
| AI images and clips | `tools/zb.py`, `tools/zfetch.py` (Higgsfield) |
| Photos | `tools/photo_search.py`, `tools/photo_get.py` (Commons, licences checked) |
| Animated maps and diagrams | `tools/gfx.py` |
| Edit | `tools/edit.py plan / prep / video / audio / mux` |
| Sound design | `tools/sfx.py`, `tools/cues.py` |
| Quality control | `tools/qc.py` |
| Upload package | `tools/package.py` |

## What the editor does (mapped to the brief)
- **Picture follows narration**: cuts snap to sentence boundaries (`qc.py` reports the share). Long holds become "beats":
  a wide framing, then detail framings found from faces/visual interest, so pictures rarely sit unchanged for more than about 8 s.
- **Motion per shot**: push to the point of interest, pull-back reveals, pans, tilts, tracking with depth parallax, crane,
  aerial push, document scans, rack focus driven by the depth map, handheld in combat. The same move is never used twice in a row.
- **Transitions per cut**: dissolves, dips to black, directional wipes for graphics, zoom-throughs into details and map
  locations, focus pulls on portraits and quotes, smoke reveals at night, film-burn in fire scenes, light flashes on impacts,
  hard cuts inside fast combat. The same special effect is never used twice in a row.
- **Motion graphics**: 32 animated maps (territories grow, routes draw themselves, locations pulse, camera pushes to the
  place being discussed), 10 animated diagrams (harbours, corvus, Trebia, Lake Trasimene, Cannae in three phases, Zama,
  the walls, the siege, the new channel, the Byrsa streets), animated timelines, counting statistic cards, split-screen
  comparisons, quote cards, lower thirds, chapter cards.
- **Sound**: ambience follows each scene's grade; sea, marching and crowds follow the picture; impacts on flash cuts,
  whooshes into graphics, ticks on timeline dates, paper on documents; riser, heartbeat and drone for Cannae and the fall.
  Music ducked under the voice, loudness normalised.

## Historical accuracy
`research.md` holds the sources and a claim register. AI reconstructions are reviewed shot by shot; anachronisms are
cropped or dropped in `edit.json` (a dome, a modern pier, a pointed arch, cursive handwriting, a paper codex).
Myths are flagged on screen (salt, Dido and Aeneas) and uncertain identifications are said to be uncertain (Hannibal's portrait).
