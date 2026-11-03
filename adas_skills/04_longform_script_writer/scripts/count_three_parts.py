#!/usr/bin/env python3
from pathlib import Path
import sys, unicodedata, json

def count(path):
    t=Path(path).read_text(encoding='utf-8',errors='replace')
    t=unicodedata.normalize('NFC',t)
    return sum(1 for ch in t if unicodedata.category(ch)[0] in {'L','N'})

if len(sys.argv)!=4:
    raise SystemExit('usage: count_three_parts.py part_a.txt part_b.txt part_c.txt')
cs=[count(x) for x in sys.argv[1:]]
mins=[13334,13334,13334]; maxs=[16000,17000,17000]
part_status=[('PASS' if mins[i] <= cs[i] <= maxs[i] else 'FAIL') for i in range(3)]
total=sum(cs)
print(json.dumps({
    'part_a':cs[0],'part_b':cs[1],'part_c':cs[2],
    'part_status':part_status,'total':total,
    'total_status':'PASS' if 40001 <= total <= 50000 else 'FAIL'
},ensure_ascii=False))
