"""Download finished Z Image jobs: python3 tools/zget.py IDX:hf_name [...]  (IDX = position in build/zqueue.json)"""
import os, sys, json, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
q = json.load(open(os.path.join(ROOT, 'build', 'zqueue.json')))
BASE = 'https://d8j0ntlcm91z4.cloudfront.net/user_3Mc7GAxjMygvfwG6Iy4auLp26uo/'
for a in sys.argv[1:]:
    i, name = a.split(':'); sid = q[int(i)]['id']
    out = os.path.join(ROOT, 'build', 'gen', f'z_{sid}.png')
    subprocess.run(['curl', '-sSfo', out, BASE + name + '.png'], check=True); print(sid)
