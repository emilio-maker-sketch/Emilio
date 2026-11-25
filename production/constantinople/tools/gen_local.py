"""Free local keyframes with RealVisXL V5 Lightning (openrail++) on CPU, bf16.

  python3 tools/gen_local.py SHOT_ID [SHOT_ID ...]   # specific shots
  python3 tools/gen_local.py --source local           # every shot assigned to the local generator
Writes build/gen/<shot>.png (1344x768, upscaled later in the edit). Skips shots already done.
"""
import os, sys, json, time, zlib, torch
from diffusers import StableDiffusionXLPipeline, DPMSolverMultistepScheduler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'gen')
MODEL = '/home/user/models/realvis'
STEPS, CFG, W, H = 6, 1.5, 1344, 768

def short_prompt(s):
    # SDXL's CLIP encoders read ~77 tokens: put the shot first, then look and grade.
    bible = json.load(open(os.path.join(ROOT, 'bible.json')))
    refs = '; '.join(bible['refs'][r] for r in s['refs'])
    return (f"cinematic film still, photorealistic, {s['desc']}. {refs}. {bible['grades'].get(s['grade'], '')}, "
            "anamorphic lens, film grain, 15th century, historically accurate")

def main():
    shots = json.load(open(os.path.join(ROOT, 'shots.json')))
    args = sys.argv[1:]
    if args[:1] == ['--source']:
        todo = [s for s in shots if s.get('source') == args[1]]
    else:
        todo = [s for s in shots if s['id'] in args]
    os.makedirs(OUT, exist_ok=True)
    torch.set_num_threads(os.cpu_count())
    pipe = StableDiffusionXLPipeline.from_pretrained(MODEL, torch_dtype=torch.bfloat16, variant='fp16', use_safetensors=True)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config, use_karras_sigmas=True, algorithm_type='sde-dpmsolver++')
    neg = json.load(open(os.path.join(ROOT, 'bible.json')))['style']['negative']
    for s in todo:
        out = os.path.join(OUT, s['id'] + '.png')
        if os.path.exists(out): continue
        t = time.time()
        g = torch.Generator().manual_seed(zlib.crc32(s['id'].encode()))
        img = pipe(prompt=short_prompt(s), negative_prompt=neg, num_inference_steps=STEPS, guidance_scale=CFG,
                   width=W, height=H, generator=g).images[0]
        img.save(out); print(s['id'], f'{time.time() - t:.0f}s', flush=True)

if __name__ == '__main__': main()
