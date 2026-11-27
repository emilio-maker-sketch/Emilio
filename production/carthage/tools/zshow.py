import json,sys,os
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
r=json.load(open(os.path.join(R,'build','zreq_all.json')));t=json.load(open(os.path.join(R,'build','ztodo.json')))
k=int(sys.argv[1])
for i in t[k*8:k*8+8]: print(i,'|',r[i]['prompt'].replace('Photorealistic cinematic historical film still, anamorphic, film grain. ','').replace(' 3rd-2nd century BC, realistic, no text.',''))
