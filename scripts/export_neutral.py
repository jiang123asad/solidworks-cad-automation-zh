"""Export using current SolidWorks session preferences; does not verify importer compatibility."""
import argparse
from pathlib import Path
import sys
import swlib
from batch_support import expand_inputs, plan_outputs, staged_file

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('files', nargs='+')
    ap.add_argument('--out', required=True)
    ap.add_argument('--fmt', default='x_t,step')
    args = ap.parse_args()
    try:
        fmts = ['.' + s.strip().lower().lstrip('.') for s in args.fmt.split(',')]
        if not fmts or any(s not in ('.x_t','.step','.stp','.igs','.iges') for s in fmts):
            raise ValueError('Formats: x_t,step,stp,igs,iges')
        files = expand_inputs(args.files, ('.sldprt','.sldasm'))
        plan_outputs(files, args.out, fmts)
    except (ValueError, OSError) as exc:
        ap.error(str(exc))
    sw = swlib.app()
    failed = 0
    for src in files:
        try:
            with swlib.owned_doc(sw, src) as raw:
                doc = swlib.model(raw)
                for ext in fmts:
                    out = Path(args.out).resolve() / (src.stem + ext)
                    try:
                        with staged_file(out) as staged:
                            swlib.save_as(doc, staged)
                        print('EXPORTED', out, '(save/file check only)')
                    except Exception as exc:
                        failed += 1
                        print('ERROR', out, exc)
        except Exception as exc:
            failed += 1
            print('ERROR', src, exc)
    return 1 if failed else 0

if __name__ == '__main__':
    sys.exit(main())
