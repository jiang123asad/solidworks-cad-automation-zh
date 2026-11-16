"""Read-only dependency checks; --connect additionally starts/connects to SW."""
import argparse
import importlib.util
import platform
import sys

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--connect', action='store_true')
    args = ap.parse_args()
    checks = [('Windows', sys.platform == 'win32'), ('Python >=3.9', sys.version_info >= (3,9))]
    for name in ('pythoncom', 'win32com'):
        checks.append((name, importlib.util.find_spec(name) is not None))
    print('Python:', sys.executable, platform.python_version())
    for name, ok in checks:
        print(('PASS ' if ok else 'FAIL ') + name)
    for name in ('PIL', 'numpy'):
        print('OPTIONAL', name, bool(importlib.util.find_spec(name)))
    if not all(ok for _, ok in checks):
        return 1
    import swlib
    try:
        print('TLB:', swlib._tlb_path())
        if args.connect:
            sw = swlib.app()
            print('Connected; revision:', sw.RevisionNumber())
    except Exception as exc:
        print('FAIL', exc)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
