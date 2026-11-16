"""Render a closed input model to a new PNG file."""
import argparse
from pathlib import Path
import sys
import swlib
from batch_support import staged_file

VIEWS = {'iso':('*Isometric',7),'front':('*Front',1),'top':('*Top',5),'right':('*Right',3)}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('file')
    ap.add_argument('output')
    ap.add_argument('view',choices=VIEWS,default='iso',nargs='?')
    args = ap.parse_args()
    if Path(args.output).suffix.lower() != '.png':
        ap.error('Output must be PNG')
    if Path(args.output).exists():
        ap.error('Output already exists')
    sw = swlib.app()
    with swlib.owned_doc(sw,args.file) as raw:
        doc = swlib.model(raw)
        doc.ShowNamedView2(*VIEWS[args.view])
        doc.ViewZoomtofit2()
        doc.ClearSelection2(True)
        with staged_file(args.output) as staged:
            swlib.save_bmp(doc,staged)
    print('SAVED',Path(args.output).resolve())
    return 0

if __name__ == '__main__':
    sys.exit(main())
