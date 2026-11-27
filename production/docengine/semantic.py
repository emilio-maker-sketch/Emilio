"""Semantic image/text matching with CLIP ViT-B/16 (ONNX, CPU).

Used for two things:
  * picking visuals: rank a pool of candidate images against what the narration is saying;
  * checking visuals: score what is actually on screen against the sentence being spoken.

Embeddings are cached on disk (keyed by path + mtime) so a 3,000-image pool is embedded once.
"""
import os, json, hashlib
import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(ROOT, 'models', 'clip16')
CACHE = os.path.join(ROOT, 'build', 'clip_cache.npz')
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)

_T = _V = _TOK = None
_cache = None


def _load():
    global _T, _V, _TOK
    if _T is None:
        import onnxruntime as ort
        from tokenizers import Tokenizer
        so = ort.SessionOptions(); so.intra_op_num_threads = max(1, (os.cpu_count() or 2) - 1)
        _T = ort.InferenceSession(os.path.join(MD, 'onnx', 'text_model.onnx'), so)
        _V = ort.InferenceSession(os.path.join(MD, 'onnx', 'vision_model.onnx'), so)
        _TOK = Tokenizer.from_file(os.path.join(MD, 'tokenizer.json'))


def _norm(x):
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-8)


def embed_text(texts):
    """List of strings -> (n, 512) unit vectors. Long strings are truncated to CLIP's 77 tokens."""
    _load()
    out = []
    for t in texts:
        ids = _TOK.encode(t.lower()).ids
        if len(ids) > 77: ids = ids[:76] + [ids[-1]]
        out.append(_T.run(None, {'input_ids': np.array([ids], np.int64)})[0][0])
    return _norm(np.array(out, np.float32))


def _prep(img_bgr):
    h, w = img_bgr.shape[:2]; s = 224 / min(h, w)
    im = cv2.resize(img_bgr, (max(224, round(w * s)), max(224, round(h * s))), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    h, w = im.shape[:2]; y, x = (h - 224) // 2, (w - 224) // 2
    im = im[y:y + 224, x:x + 224, ::-1].astype(np.float32) / 255.0
    return ((im - MEAN) / STD).transpose(2, 0, 1)


def _views(img):
    """Centre crop misses half of a wide painting, so embed the whole frame (padded) plus the centre crop."""
    h, w = img.shape[:2]; m = max(h, w)
    pad = np.full((m, m, 3), int(np.median(img)), np.uint8)
    pad[(m - h) // 2:(m - h) // 2 + h, (m - w) // 2:(m - w) // 2 + w] = img
    return [_prep(pad), _prep(img)]


def embed_images(imgs):
    """List of BGR uint8 arrays -> (n, 512) unit vectors (mean of whole-frame and centre-crop views)."""
    _load()
    out = []
    for im in imgs:
        v = _V.run(None, {'pixel_values': np.stack(_views(im))})[0]
        out.append(_norm(v).mean(0))
    return _norm(np.array(out, np.float32))


def _key(path):
    st = os.stat(path)
    return hashlib.md5(f'{os.path.abspath(path)}|{st.st_mtime_ns}|{st.st_size}'.encode()).hexdigest()


def _cache_load():
    global _cache
    if _cache is None:
        _cache = {}
        if os.path.exists(CACHE):
            z = np.load(CACHE)
            _cache = {k: z[k] for k in z.files}
    return _cache


def cache_save():
    if _cache is not None:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        np.savez(CACHE + '.tmp.npz', **_cache); os.replace(CACHE + '.tmp.npz', CACHE)


def embed_files(paths, verbose=False):
    c = _cache_load(); keys = [_key(p) for p in paths]; todo = [i for i, k in enumerate(keys) if k not in c]
    for n, i in enumerate(todo):
        im = cv2.imread(paths[i], cv2.IMREAD_COLOR)
        if im is None: c[keys[i]] = np.zeros(512, np.float32); continue
        c[keys[i]] = embed_images([im])[0]
        if verbose and n % 50 == 0: print(f'  embedded {n}/{len(todo)}', flush=True)
    if todo: cache_save()
    return np.array([c[k] for k in keys], np.float32)


def prompts(sentence, context=''):
    """A spoken sentence is not an image caption: wrap it so CLIP compares like with like."""
    s = sentence.strip()
    out = [f'a photograph or artwork showing: {s}', s]
    if context: out.append(f'{context}: {s}')
    return out


def text_vec(sentence, context=''):
    v = embed_text(prompts(sentence, context)).mean(0)
    return v / (np.linalg.norm(v) + 1e-8)


def score(text_v, img_v):
    """Cosine similarity * 100 (CLIP logit scale). ~>27 strong, 22-27 plausible, <20 weak for this model."""
    return float(np.dot(text_v, img_v) * 100)


if __name__ == '__main__':
    import sys
    paths = sys.argv[2:]; tv = text_vec(sys.argv[1])
    for p, v in zip(paths, embed_files(paths)):
        print(f'{score(tv, v):6.2f}  {p}')
