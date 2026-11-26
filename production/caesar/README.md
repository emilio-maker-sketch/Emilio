# The Ides of March: The Assassination of Julius Caesar

Second long-form documentary in the series. About 58 minutes, 16:9, 1080p30.

## Budget
Higgsfield credits: **29.20 of 30** (see `credits_ledger.md`)
- 128 Z Image reconstructions at 0.15 credits each: 19.20
- 5 Seedance 2.0 Mini image-to-video clips (4 s, 480p, upscaled): 10.00

Everything else is free:
- narration: Kokoro `bm_lewis`, local
- music: Kevin MacLeod, CC BY 4.0
- real photos, sculpture, coins and paintings: Wikimedia Commons, PD and CC, credited
- maps: Natural Earth
- sound effects: synthesized

## What is new in the edit (vs. *The Last Day of Rome*)
- **AI video clips** at five hero moments:
  - Caesar's sleepless night
  - the Rubicon
  - the senators closing in
  - the funeral fire
  - the comet

  Each clip is slowed with frame blending to fit its shot, then upscaled and sharpened.
- **Animated maps:** campaign routes draw themselves on, with arrowheads.
- **Quote cards:** the key lines from Suetonius, Plutarch and Cicero appear on screen with their source, over a blurred plate of the scene, with a low hit.
- **Name titles** (lower thirds) when Brutus, Cassius, Decimus, Calpurnia, Cicero, Antony and Octavius are introduced.
- **Transitions and framing:**
  - a light-leak sweep and a whoosh into every chapter card
  - letterbox bars for the two climax chapters
  - a riser, a heartbeat and an impact into the murder
- **Sound design:** synthesized ambience matched to each scene:
  - crowd murmur in the Forum
  - marching feet
  - sea and waves
  - fire, wind, night and drones
- **Atmosphere:** floating dust in lamplit and sunlit scenes.
- **Real sources on screen:**
  - the Tusculum and Chiaramonti portraits
  - the busts of Pompey, Crassus, Cicero, Cato, Brutus and Antony
  - the coins: EID MAR, DICT PERPETVO, the comet denarius
  - Gérôme and Camuccini's paintings
  - Largo di Torre Argentina today

## Files
| File | What it is |
|---|---|
| `research.md` | Sources and claim register (Solid / Reported / Disputed) |
| `script/*.md` | 17 chapter files: narration plus shot lines |
| `bible.json` | Look and character references |
| `edit.json` | Shot overrides |
| `tools/` | The pipeline: narration, image queue, Commons, maps, sound effects, cues, editor, package |

## Known limitations
- The AI clips are 480p, upscaled. They are used briefly and graded to match.
- Some reconstructions show small anachronisms:
  - legionary armour closer to the imperial period
  - a quill pen
  - a few senators with stubble
- Character likeness varies between shots, because the image model has no reference lock.
