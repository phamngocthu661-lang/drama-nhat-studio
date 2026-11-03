#!/usr/bin/env python3
from pathlib import Path
import sys,unicodedata,json

def c(p):
    t=Path(p).read_text(encoding='utf-8',errors='replace')
    t=unicodedata.normalize('NFC',t)
    return sum(1 for ch in t if unicodedata.category(ch)[0] in {'L','N'})
if len(sys.argv)!=4: raise SystemExit('usage: part_precheck.py A.txt B.txt C.txt')
cs=[c(x) for x in sys.argv[1:]]
mins=[13334]*3; maxs=[16000,17000,17000]
ps=[mins[i] <= cs[i] <= maxs[i] for i in range(3)]
t=sum(cs)
print(json.dumps({'A':cs[0],'B':cs[1],'C':cs[2],'part_pass':ps,'total':t,'total_pass':40001<=t<=50000,'ready_for_audit':all(ps) and 40001<=t<=50000},ensure_ascii=False))
