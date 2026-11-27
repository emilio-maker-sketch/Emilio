import json,sys,os
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
r=json.load(open(os.path.join(R,'build','zreq_all.json')))
k=int(sys.argv[1]);out=[{"index":i,"params":{"model":"z_image","aspect_ratio":"16:9","prompt":x['prompt']}} for i,x in enumerate(r) if k*12<=i<k*12+12]
print(json.dumps(out,ensure_ascii=False))
