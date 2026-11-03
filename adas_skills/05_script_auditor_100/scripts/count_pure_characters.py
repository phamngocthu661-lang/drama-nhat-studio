#!/usr/bin/env python3
"""Deterministic pure-character counter for Japanese narration scripts.
Counts Unicode Letters/Numbers after NFC normalization; excludes punctuation, symbols and whitespace.
"""
from pathlib import Path
import argparse, unicodedata, json

def pure_count(text: str) -> int:
    text = unicodedata.normalize("NFC", text)
    return sum(1 for ch in text if unicodedata.category(ch)[0] in {"L", "N"})

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("path")
    args=ap.parse_args()
    p=Path(args.path)
    text=p.read_text(encoding="utf-8", errors="replace")
    count=pure_count(text)
    if count <= 40000:
        status="FAIL_BELOW_MINIMUM"
    elif count > 50000:
        status="FAIL_ABOVE_MAXIMUM"
    else:
        status="PASS"
    print(json.dumps({"file":str(p),"pure_character_count":count,"minimum":40001,"maximum":50000,"status":status}, ensure_ascii=False))

if __name__ == "__main__": main()
