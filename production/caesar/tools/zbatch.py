import json,sys
r=json.load(open('/tmp/claude-0/-home-user-Emilio/67ec79ed-16a1-5f80-9506-8610db2238f5/scratchpad/zreq.json'))
k=int(sys.argv[1]); print(json.dumps(r[k*8:k*8+8],ensure_ascii=False))
