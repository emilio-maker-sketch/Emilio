# Technical QC - Nineveh.mp4 (13:22.8)

| check | status | result |
|---|---|---|
| decode | PASS | 0 decode errors |
| black | PASS | 0 black stretches > 0.6 s (excluding open/close) |
| freeze | PASS | 0 frozen stretches >= 4 s |
| strobe | PASS | 15 hard cuts; 0 clusters of >3 cuts in 2 s |
| loudness | PASS | integrated -14.0 LUFS, range 2.3 LU, true peak -1.4 dBTP (target -14 LUFS, <= -1 dBTP) |
| static | PASS | 0 stretches >= 8 s with almost no visual change |
| look | WARN | median luma 0.29, saturation 0.31; 4 outlier stretches |
| balance | PASS | speech -13.0 dB, bed in pauses -19.5 dB -> pauses sit 6.4 dB under speech (target 6-22) |
| subtitles | PASS | 187 cues; caption start vs exact sentence start: median 0.000s, 95th pct 0.000s; 0 too fast (>21 cps); 0 lines > 42 chars |
| spelling | PASS | 100 on-screen strings, 0 unknown words |
| images | WARN | 18 images: 1 soft upscales, 0 near-duplicate pairs |

### look
- 1:10.0-1:28.0 luma 0.41 sat 0.4
- 2:32.0-2:34.0 luma 0.09 sat 0.4
- 5:59.5-5:59.5 luma 0.09 sat 0.41
- 12:52.5-12:52.5 luma 0.06 sat 0.46

### images
- met328922 800x525 shown on board (upscale 1.8x)
