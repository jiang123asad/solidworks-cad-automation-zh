"""Screen part directories by summary metrics, not proof of geometry equivalence."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys
import swlib

def collect(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Expected directory: %s' % root)
    out = {}
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.suffix.lower() in ('.sldprt','.sldasm') and not path.name.startswith('~$'):
            key = path.relative_to(root).as_posix().casefold()
            if key in out:
                raise ValueError('Case-insensitive path collision: %s' % key)
            out[key] = path
    return out

def metrics(sw, path):
    with swlib.owned_doc(sw, path) as raw:
        doc = swlib.model(raw)
        boxes = [list(b.GetBodyBox()) for b in swlib.bodies(raw)]
        bounds = ([min(b[i] for b in boxes)*1000 for i in range(3)] +
                  [max(b[i] for b in boxes)*1000 for i in range(3,6)]) if boxes else None
        return {'volume': swlib.total_volume(raw), 'faces': swlib.total_faces(raw),
                'bodies': len(boxes), 'box_mm': bounds,
                'features': [(t,n,d) for t,n,d in swlib.walk_features(doc)]}

def classify(a, b, volume_tol=1.0, length_tol=0.01):
    box_changed = (a['box_mm'] is None) != (b['box_mm'] is None)
    if a['box_mm'] is not None and b['box_mm'] is not None:
        box_changed = any(abs(x-y) > length_tol for x,y in zip(a['box_mm'],b['box_mm']))
    if (abs(b['volume']-a['volume']) > volume_tol or a['faces'] != b['faces'] or
            a['bodies'] != b['bodies'] or box_changed):
        return 'METRICS_DIFFER'
    if Counter(tuple(f) for f in a['features']) != Counter(tuple(f) for f in b['features']):
        return 'FEATURES_DIFFER'
    return 'NO_DIFFERENCE_DETECTED'

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('old')
    ap.add_argument('new')
    ap.add_argument('--out', default='diff.txt')
    ap.add_argument('--json', dest='json_out')
    ap.add_argument('--volume-tol', type=float, default=1.0)
    ap.add_argument('--length-tol', type=float, default=0.01)
    args = ap.parse_args()
    if not all(math.isfinite(x) and x >= 0 for x in (args.volume_tol,args.length_tol)):
        ap.error('Tolerances must be finite and nonnegative')
    try:
        a,b = collect(args.old),collect(args.new)
        reports = [Path(args.out).resolve()] + ([Path(args.json_out).resolve()] if args.json_out else [])
        if len(set(reports)) != len(reports):
            raise ValueError('Report paths must be distinct')
        for p in reports:
            if p.exists():
                raise FileExistsError(p)
    except (ValueError,OSError) as exc:
        ap.error(str(exc))
    keys = sorted(set(a)|set(b))
    if not keys:
        print('No parts or assemblies found')
        return 1
    sw = swlib.app()
    records = []
    for key in keys:
        rec = {'name':key}
        if key not in a:
            rec['status'] = 'ONLY_NEW'
        elif key not in b:
            rec['status'] = 'ONLY_OLD'
        elif a[key].suffix.lower() != '.sldprt':
            rec.update(status='UNSUPPORTED', reason='Assembly geometry adapter not implemented')
        else:
            try:
                ma,mb = metrics(sw,a[key]),metrics(sw,b[key])
                rec.update(status=classify(ma,mb,args.volume_tol,args.length_tol),old=ma,new=mb,
                           dV=mb['volume']-ma['volume'],dFaces=mb['faces']-ma['faces'])
            except Exception as exc:
                rec.update(status='ERROR',reason=str(exc))
        records.append(rec)
        print(rec['status'],key,rec.get('reason',''))
        for p in reports:
            p.parent.mkdir(parents=True,exist_ok=True)
        # Checkpoint after every file; these paths were reserved by preflight.
        reports[0].write_text('\n'.join(r['status']+'  '+r['name']+'  '+r.get('reason','') for r in records)+'\n',encoding='utf-8')
        if args.json_out:
            reports[1].write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print('NO_DIFFERENCE_DETECTED is only a metric screen; compare target dimensions for critical changes.')
    return int(any(r['status'] in ('ERROR','UNSUPPORTED') for r in records))

if __name__ == '__main__':
    sys.exit(main())
