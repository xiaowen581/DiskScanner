#!/usr/bin/env python3
"""Build helper: resolve scanner_core .pyd and __init__.py paths for PyInstaller."""
import importlib.util
import glob
import os
import sys

spec = importlib.util.find_spec('scanner_core')
if spec is None or spec.origin is None:
    print("ERROR: scanner_core not found", file=sys.stderr)
    sys.exit(1)

pkg_dir = os.path.dirname(spec.origin)
pyd_files = glob.glob(os.path.join(pkg_dir, '*.pyd')) + glob.glob(os.path.join(pkg_dir, '*.so'))
if not pyd_files:
    print(f"ERROR: no .pyd/.so found in {pkg_dir}", file=sys.stderr)
    sys.exit(1)

# Output batch-compatible variable assignments
print(f"SCANNER_PYD={pyd_files[0]}")
print(f"SCANNER_INIT={os.path.join(pkg_dir, '__init__.py')}")
