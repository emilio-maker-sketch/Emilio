"""python3 tools/zdl.py IDX=url_or_name ... downloads z images by zreq_all index."""
import os,sys,json,subprocess
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
q=json.load(open(os.path.join(R,'build','zreq_all.json')))
BASE='https://d8j0ntlcm91z4.cloudfront.net/user_3Mc7GAxjMygvfwG6Iy4auLp26uo/'
os.makedirs(os.path.join(R,'build','gen'),exist_ok=True)
for a in sys.argv[1:]:
    i,name=a.split('=',1);sid=q[int(i)]['id']
    url=name if name.startswith('http') else BASE+name+'.png'
    out=os.path.join(R,'build','gen',f'z_{sid}.png')
    subprocess.run(['curl','-sSfo',out,url],check=True)
    open(os.path.join(R,'build','gen','log.txt'),'a').write(f'{sid} {url}\n');print(sid,end=' ')
print()
