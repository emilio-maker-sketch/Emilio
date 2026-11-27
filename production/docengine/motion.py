"""Content-aware camera moves for still images (replaces index-based Ken Burns).

plan(img, dur, mood, prev) analyses the picture once and chooses a move that suits it:
  push_face   - slow push toward a detected face (portraits, statues)
  push_focus  - push toward the salient subject (objects, details)
  pull_reveal - start tight on the subject and pull back to reveal the whole (discoveries)
  pan / tilt  - travel along the long axis of wide/tall images, ending on the subject
  parallax    - 2.5D dolly using a monocular depth map (scenes with real depth: landscapes, interiors)
Mood ('calm' | 'tense' | 'reveal' | 'somber') sets speed and amplitude. The planner never repeats the previous move
if an alternative suits the image, so consecutive stills don't all move the same way.
"""
import os, math
import numpy as np, cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1920, 1080
_DEPTH = None
_FACE = None


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (6 * x - 15) + 10)          # smootherstep: no visible start/stop jolt


def glide(u):
    """Mostly linear (motion never stalls) with eased ends."""
    return .65 * u + .35 * ease(u)


# ------------------------------------------------------------------ analysis
def saliency(img):
    """Spectral-residual saliency (Hou & Zhang 2007), returns (map HxW float 0..1)."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    s = cv2.resize(g, (96, int(96 * g.shape[0] / g.shape[1])) if g.shape[1] > g.shape[0] else (int(96 * g.shape[1] / g.shape[0]), 96))
    F = np.fft.fft2(s); amp = np.log(np.abs(F) + 1e-6); ph = np.angle(F)
    res = amp - cv2.blur(amp, (3, 3))
    sal = np.abs(np.fft.ifft2(np.exp(res + 1j * ph))) ** 2
    sal = cv2.GaussianBlur(sal, (0, 0), 2.5)
    # downweight borders (frames, mounts, museum backdrops) and blend with local contrast
    h, w = sal.shape; yy, xx = np.mgrid[0:h, 0:w]
    border = np.clip(np.minimum.reduce([xx, yy, w - 1 - xx, h - 1 - yy]) / (0.08 * max(h, w)), 0, 1)
    sal = sal * border
    sal = (sal - sal.min()) / (sal.max() - sal.min() + 1e-6)
    return cv2.resize(sal, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)


def focus_point(sal):
    thr = np.percentile(sal, 92); m = sal >= thr
    ys, xs = np.nonzero(m)
    if len(xs) == 0: return .5, .5, (0, 0, 1, 1)
    h, w = sal.shape
    x0, x1 = np.percentile(xs, (5, 95)) / w; y0, y1 = np.percentile(ys, (5, 95)) / h
    wts = sal[m]
    return float((xs * wts).sum() / wts.sum() / w), float((ys * wts).sum() / wts.sum() / h), (x0, y0, x1, y1)


def faces(img):
    """YuNet DNN face detector (works on paintings and statues better than Haar). Returns [(x, y, w, h)] largest first."""
    global _FACE
    p = os.path.join(ROOT, 'models', 'yunet', 'yunet.onnx')
    if not os.path.exists(p): return []
    s = 640 / max(img.shape[:2]); im = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img
    s = min(1.0, s); h, w = im.shape[:2]
    if _FACE is None: _FACE = cv2.FaceDetectorYN.create(p, '', (w, h), 0.75, 0.3, 50)
    _FACE.setInputSize((w, h))
    _, det = _FACE.detect(im)
    if det is None: return []
    out = [(d[0] / s, d[1] / s, d[2] / s, d[3] / s) for d in det]
    out.sort(key=lambda r: -r[2] * r[3])
    return out[:1]


def depth(img):
    """Depth Anything (small, ONNX). Returns HxW float 0 (far) .. 1 (near), or None if the model is unavailable."""
    global _DEPTH
    p = os.path.join(ROOT, 'models', 'depth', 'onnx', 'model.onnx')
    if not os.path.exists(p): return None
    if _DEPTH is None:
        import onnxruntime as ort
        _DEPTH = ort.InferenceSession(p)
    h, w = img.shape[:2]; s = 518 / max(h, w)
    nh, nw = max(14, int(round(h * s / 14)) * 14), max(14, int(round(w * s / 14)) * 14)
    x = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)[..., ::-1].astype(np.float32) / 255
    x = ((x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]).transpose(2, 0, 1)[None].astype(np.float32)
    d = _DEPTH.run(None, {'pixel_values': x})[0][0]
    d = cv2.resize(d, (w, h), interpolation=cv2.INTER_CUBIC)
    lo, hi = np.percentile(d, (2, 98))
    return np.clip((d - lo) / (hi - lo + 1e-6), 0, 1).astype(np.float32)


def plain_background(img):
    """Museum object on a seamless backdrop? (border nearly uniform)"""
    b = np.concatenate([img[:12].reshape(-1, 3), img[-12:].reshape(-1, 3), img[:, :12].reshape(-1, 3), img[:, -12:].reshape(-1, 3)]).astype(np.float32)
    return float(b.std(axis=0).mean()) < 14


def analyse(img):
    sal = saliency(img); fx, fy, box = focus_point(sal)
    fc = faces(img)
    a = {'focus': (fx, fy), 'box': box, 'face': None, 'plain': plain_background(img), 'depth': None, 'depth_spread': 0.0}
    h, w = img.shape[:2]
    if fc:
        x, y, fw, fh = fc[0]
        if fw * fh / (w * h) > .006: a['face'] = ((x + fw / 2) / w, (y + fh * .45) / h, fw / w)
    if not a['plain']:
        d = depth(img)
        if d is not None:
            a['depth'] = d
            # useful parallax needs a real near/far separation, not just a gradient
            a['depth_spread'] = float(np.percentile(d, 85) - np.percentile(d, 15))
    return a


# ------------------------------------------------------------------ planning
MOODS = {'calm': (.075, 1.0), 'reveal': (.16, 1.0), 'tense': (.12, 1.35), 'somber': (.06, .8)}


def trim_mount(img):
    """Remove uniform borders (photo mounts, scan margins, museum card edges) so they never show on screen."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = g.shape
    def edge(lines, n):
        ref = np.median(lines[:max(2, n // 50)], axis=0)
        for i in range(int(n * .2)):
            ln = lines[i]
            if ln.std() > 18 or np.abs(ln - ref).mean() > 22: return i
        return int(n * .2)
    top = edge(g, h); bot = edge(g[::-1], h); lef = edge(g.T, w); rig = edge(g.T[::-1], w)
    if top + bot > h * .35 or lef + rig > w * .35: return img
    pad = 4
    return img[top + pad if top else 0:h - bot - pad if bot else h, lef + pad if lef else 0:w - rig - pad if rig else w]


def plan(img, dur, mood='calm', prev=None, hint=None, trim=True):
    if trim and not plain_background(img): img = trim_mount(img)
    a = analyse(img)
    h, w = img.shape[:2]; ar = w / h
    slack_x = max(0.0, ar / (W / H) - 1); slack_y = max(0.0, (W / H) / ar - 1)
    cand = []
    if hint: cand.append(hint)
    if mood == 'reveal': cand.append('pull_reveal')
    if a['face'] and a['face'][2] > .06: cand.append('push_face')
    if a['depth'] is not None and a['depth_spread'] > .32 and not a['plain']: cand.append('parallax')
    if slack_x > .25: cand.append('pan')
    if slack_y > .45: cand.append('tilt')
    cand += ['push_focus', 'pull_reveal']
    choice = next((c for c in cand if c != prev), cand[0])
    amp, spd = MOODS.get(mood, MOODS['calm'])
    return Move(img, a, choice, dur, amp, spd)


class Move:
    def __init__(self, img, a, kind, dur, amp, spd):
        self.kind, self.a, self.dur = kind, a, dur
        h, w = img.shape[:2]
        # cover the frame with some headroom for the move; never stretch (uniform scale only)
        self.s0 = max(W / w, H / h)
        head = 1.0 + amp * spd + (.06 if kind in ('pan', 'tilt', 'parallax') else .02)
        s = self.s0 * head
        self.big = cv2.resize(img, (int(w * s) + 2, int(h * s) + 2), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        self.bh, self.bw = self.big.shape[:2]
        self.amp, self.spd = amp, spd
        fx, fy = a['face'][:2] if (kind == 'push_face' and a['face']) else a['focus']
        self.fx, self.fy = fx, fy
        if kind == 'parallax':
            d = cv2.resize(a['depth'], (self.bw, self.bh), interpolation=cv2.INTER_LINEAR)
            self.d = cv2.GaussianBlur(d, (0, 0), 6)
            self.dir = 1 if fx < .5 else -1
        self.pan_dir = 1 if fx > .5 else -1      # travel toward the subject, end on it

    def _view(self, cx, cy, z):
        """Affine for a window centred at (cx, cy) in big-image px, zoom z (1 = big image fills at base scale)."""
        sc = z * (self.s0 * 1.0) / (self.s0 * (self.bw / (self.bw)))  # big already includes base scale
        sc = z
        tx = W / 2 - cx * sc; ty = H / 2 - cy * sc
        # clamp so we never show outside the picture
        tx = min(0, max(W - self.bw * sc, tx)); ty = min(0, max(H - self.bh * sc, ty))
        return np.float32([[sc, 0, tx], [0, sc, ty]])

    def frame(self, t):
        u = glide(min(1.0, max(0.0, t / max(.01, self.dur))))
        k, bw, bh = self.kind, self.bw, self.bh
        zmin = max(W / bw, H / bh)                       # zoom at which the big image exactly covers the frame
        A = self.amp * self.spd
        if k == 'push_focus' and self.a['plain']:
            x0, y0, x1, y1 = self.a['box']; oh = max(.05, y1 - y0) * bh; ow = max(.05, x1 - x0) * bw
            zend = min(.62 * H / oh, .62 * W / ow, zmin * 2.2); zst = max(zmin * 1.02, zend * .82)
            z = zst + (zend - zst) * u
            cx = bw / 2 + ((x0 + x1) / 2 * bw - bw / 2) * (.5 + .5 * u); cy = bh / 2 + ((y0 + y1) / 2 * bh - bh / 2) * (.5 + .5 * u)
        elif k == 'push_face' or k == 'push_focus':
            z = zmin * (1 + .02 + A * u)
            cx = bw / 2 + (self.fx * bw - bw / 2) * (.35 + .65 * u); cy = bh / 2 + (self.fy * bh - bh / 2) * (.35 + .65 * u)
        elif k == 'pull_reveal':
            z = zmin * (1 + .02 + A * 1.3 * (1 - u))
            cx = bw / 2 + (self.fx * bw - bw / 2) * (1 - u); cy = bh / 2 + (self.fy * bh - bh / 2) * (1 - u)
        elif k == 'pan':
            z = zmin * (1.02 + .25 * A)
            span = bw - W / z; x0 = W / z / 2
            end = min(1, max(0, (self.fx * bw - x0) / max(1, span))); start = min(1, max(0, end - .55)) if end > .5 else min(1, end + .55)
            cx = x0 + span * (start + (end - start) * u); cy = bh / 2 + (self.fy * bh - bh / 2) * .4
        elif k == 'tilt':
            z = zmin * (1.02 + .25 * A)
            span = bh - H / z; y0 = H / z / 2
            end = min(1, max(0, (self.fy * bh - y0) / max(1, span))); start = min(1, max(0, end - .5)) if end > .5 else min(1, end + .5)
            cy = y0 + span * (start + (end - start) * u); cx = bw / 2 + (self.fx * bw - bw / 2) * .4
        else:  # parallax
            z = zmin * (1.03 + A * .6 * u)
            cx = bw / 2 + self.dir * (bw - W / z) * .25 * (u - .5); cy = bh / 2
        M = self._view(cx, cy, z)
        if k != 'parallax':
            return cv2.warpAffine(self.big, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        # 2.5D: near pixels travel further than far ones as the camera trucks sideways and dollies in
        out_d = cv2.warpAffine(self.d, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        base = cv2.warpAffine(self.big, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        shift = 26 * self.spd * (u - .5) * self.dir           # px at the nearest plane
        grow = .045 * self.spd * u                            # near planes scale up faster than far ones
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        dd = out_d - .5
        mx = xx - shift * dd - (xx - W / 2) * grow * dd
        my = yy - (yy - H / 2) * grow * dd
        return cv2.remap(base, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


# ------------------------------------------------------------------ grade
def grade(img, mono=None):
    """Consistent documentary look that respects the source: exposure normalised, gentle filmic curve,
    colour kept (slightly restrained) for colour sources, warm-neutral monochrome for B&W prints. BGR uint8 in/out."""
    f = img.astype(np.float32) / 255
    lum = f[..., 0] * .114 + f[..., 1] * .587 + f[..., 2] * .299
    lo, hi = np.percentile(lum[::3, ::3], (.6, 99.4))
    gain = min(1.7, .96 / max(.25, hi - lo))
    f = np.clip((f - lo) * gain, 0, 1)
    lum = f[..., 0] * .114 + f[..., 1] * .587 + f[..., 2] * .299
    med = float(np.median(lum[::3, ::3])); g = math.log(.44) / math.log(min(.9, max(.08, med)))
    g = min(1.6, max(.65, g)); f = f ** g
    # colour vs monochrome: judge by the most colourful 5% of pixels, so a gold object on a grey backdrop stays gold
    chroma = (f.max(axis=2) - f.min(axis=2))[::3, ::3]
    if mono is None: mono = float(np.percentile(chroma, 95)) < .09
    lum = f[..., 0] * .114 + f[..., 1] * .587 + f[..., 2] * .299
    curve = lambda x: x + .18 * x * (1 - x) * (2 * x - 1) * 1.6     # soft S
    if mono:
        l = curve(lum)
        out = np.stack([l * .93 + .015, l * .98 + .01, l * 1.02], -1)     # BGR: faint warm paper tone
    else:
        f = curve(f)
        l = f.mean(axis=2, keepdims=True); f = l + (f - l) * .88            # restrained saturation
        sh = np.clip(1 - lum * 2, 0, 1)[..., None]; hl = np.clip(lum * 2 - 1, 0, 1)[..., None]
        out = f + sh * np.array([.025, .012, -.01]) + hl * np.array([-.02, .0, .022])   # teal shadows, warm highlights, subtle
    out = np.clip(out, 0, 1) * 255
    bl = cv2.GaussianBlur(out, (0, 0), 1.3)
    return np.clip(out * 1.35 - bl * .35, 0, 255).astype(np.uint8)          # light unsharp mask
