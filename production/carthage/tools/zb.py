import json,sys,os
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
r=json.load(open(os.path.join(R,'build','zreq_all.json')));t=json.load(open(os.path.join(R,'build','ztodo.json')))
k=int(sys.argv[1]);print(json.dumps([{"index":i,"params":{"model":"z_image","aspect_ratio":"16:9","prompt":r[i]['prompt']}} for i in t[k*8:k*8+8]],ensure_ascii=False))
