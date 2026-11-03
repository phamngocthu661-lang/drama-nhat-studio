#!/usr/bin/env python3
"""Mechanical precheck. Does NOT replace semantic logic audit."""
import sys,re,collections,pathlib,unicodedata,json
p=pathlib.Path(sys.argv[1]); t=p.read_text(encoding='utf-8',errors='replace')
pure=sum(1 for ch in unicodedata.normalize('NFC',t) if unicodedata.category(ch)[0] in {'L','N'})
status='PASS' if 40001 <= pure <= 50000 else ('FAIL_BELOW_MINIMUM' if pure <= 40000 else 'FAIL_ABOVE_MAXIMUM')
print('pure_character_count',pure)
print('length_gate',status)
print('raw_characters',len(t))
for x in ['しかし','すると','その瞬間','直後','凍りついた','言葉を失った','実は']:
    print(x,t.count(x))
parts=[s.strip() for s in re.split(r'[。！？\n]+',t) if len(s.strip())>=24]
c=collections.Counter(parts)
reps=[(n,s) for s,n in c.items() if n>=2]
print('repeated_long_sentences',len(reps))
for n,s in sorted(reps,reverse=True)[:20]: print(n,s[:120])
