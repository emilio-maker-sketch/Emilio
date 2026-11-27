"""python3 tools/zfetch.py now|HHMMSS IDX=jobid ... : find hf_<date>_<t>_<jobid>.png near the time, wait until it exists, download."""
import os,sys,json,subprocess,time,datetime
from concurrent.futures import ThreadPoolExecutor
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
q=json.load(open(os.path.join(R,'build','zreq_all.json')))
BASE='https://d8j0ntlcm91z4.cloudfront.net/user_3Mc7GAxjMygvfwG6Iy4auLp26uo/'
now=datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
t0=now-datetime.timedelta(seconds=90) if sys.argv[1]=='now' else datetime.datetime.combine(now.date(),datetime.datetime.strptime(sys.argv[1],'%H%M%S').time())
todo=dict(a.split('=') for a in sys.argv[2:]); deadline=time.time()+900
def head(u): return u if subprocess.run(['curl','-sfI','-o','/dev/null','-m','8',u]).returncode==0 else None
with ThreadPoolExecutor(48) as ex:
    while todo and time.time()<deadline:
        for i,j in list(todo.items()):
            urls=[f"{BASE}hf_{(t0+datetime.timedelta(seconds=dt)).strftime('%Y%m%d_%H%M%S')}_{j}.png" for dt in range(0,200)]
            hit=next((u for u in ex.map(head,urls) if u),None)
            if hit:
                sid=q[int(i)]['id']; subprocess.run(['curl','-sSfo',os.path.join(R,'build','gen',f'z_{sid}.png'),hit],check=True)
                open(os.path.join(R,'build','gen','log.txt'),'a').write(f'{sid} {j} {hit}\n'); print(sid,end=' ',flush=True); del todo[i]
        if todo: time.sleep(4)
print('\nmissing:',todo)
