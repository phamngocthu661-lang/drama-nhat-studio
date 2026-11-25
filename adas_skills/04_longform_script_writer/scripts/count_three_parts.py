#!/usr/bin/env python3
"""V4 compatibility shim: JSON output and nonzero exit on mechanical FAIL."""
import subprocess,sys
from pathlib import Path
raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).with_name('adas_v4.py')),'parts',*sys.argv[1:]]))
