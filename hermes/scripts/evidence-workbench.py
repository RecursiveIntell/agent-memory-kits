#!/usr/bin/env python3
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[2] / 'shared/scripts/evidence-workbench.py'), run_name='__main__')
