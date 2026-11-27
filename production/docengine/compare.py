"""Before/after comparison of two renders of the same documentary (run from the project dir).

python3 ../docengine/compare.py <v1.mp4> <v2.mp4> <qc_v1.json> <qc_v2.json> <audit_v1.json> <audit_v2.json> [times...]
Writes build/compare/compare.md and side-by-side stills (v1 left, v2 right).
"""
import os, sys, json, subprocess
import numpy as np, cv2

OUT = os.path.join('build', 'compare'); os.makedirs(OUT, exist_ok=True)


def frame(video, t):
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read()
    return f if ok else np.zeros((1080, 1920, 3), np.uint8)


def main():
    v1, v2, q1, q2, a1, a2 = sys.argv[1:7]
    times = [float(x) for x in sys.argv[7:]] or [60, 89, 120, 232, 326, 400, 755, 1074]
    Q1 = {r['check']: r for r in json.load(open(q1))['results']}
    Q2 = {r['check']: r for r in json.load(open(q2))['results']}
    A1, A2 = json.load(open(a1))['summary'], json.load(open(a2))['summary']
    L = ['# v1 vs v2', '', '## Technical QC', '', '| check | v1 | v2 |', '|---|---|---|']
    for k in Q2:
        L.append(f"| {k} | {Q1.get(k, {}).get('status', '-')}: {Q1.get(k, {}).get('msg', '')} | {Q2[k]['status']}: {Q2[k]['msg']} |")
    L += ['', '## Narration-to-visual accuracy', '', '| metric | v1 | v2 |', '|---|---|---|']
    for k in ('image_shots', 'mean_image_z', 'frame_z_mean'):
        L.append(f'| {k} | {A1.get(k)} | {A2.get(k)} |')
    L.append(f"| flags | {A1.get('flags')} | {A2.get('flags')} |")
    L.append(f"| low frame matches (z < -1) | {len(A1.get('frame_z_low') or [])} | {len(A2.get('frame_z_low') or [])} |")
    L += ['', '## Side by side (v1 left, v2 right)', '']
    for t in times:
        a, b = frame(v1, t), frame(v2, t)
        s = np.hstack([cv2.resize(a, (960, 540)), cv2.resize(b, (960, 540))])
        cv2.putText(s, f'{int(t // 60)}:{t % 60:04.1f}', (16, 40), 0, 1.1, (0, 255, 255), 2)
        p = os.path.join(OUT, f'side_{t:07.1f}.jpg'); cv2.imwrite(p, s)
        L.append(f'![{t}]({os.path.basename(p)})')
    open(os.path.join(OUT, 'compare.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L[:40]))


if __name__ == '__main__':
    main()
