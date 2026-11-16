"""Chamfer both external end edges in isolated part copies; refuse overwrite."""
import argparse
import math
from pathlib import Path
import sys
import swlib
from batch_support import expand_inputs,plan_outputs

def end_edge(body,idx,target,tol=0.01):
    choices = []
    for edge in swlib.edges(body):
        c = swlib.circle_of(edge)
        if c and abs(c[3+idx]) > 1-1e-6 and abs(c[idx]-target) < tol:
            choices.append((c[6],edge))
    if not choices:
        raise ValueError('No coaxial circular edge at end %g mm' % target)
    return max(choices,key=lambda c:c[0])[1]

def process(sw,src,dst,angle,width):
    with swlib.part_output(sw,src,dst) as (raw,staged):
        doc = swlib.model(raw)
        body,n = swlib.main_body(raw)
        if body is None or n != 1:
            raise ValueError('Chamfer helper requires a single solid body')
        ax = swlib.axial_axis(body)
        if ax is None:
            raise ValueError('No unambiguous XYZ-aligned rotational axis')
        idx,lo,hi = ax
        v0 = swlib.total_volume(raw)
        for target in (lo,hi):
            body,_ = swlib.main_body(raw)  # old edge references are invalid after a feature
            edge = end_edge(body,idx,target)
            doc.ClearSelection2(True)
            if not swlib.select(edge):
                raise RuntimeError('Failed to select end edge')
            before = swlib.total_volume(raw)
            feat = doc.FeatureManager.InsertFeatureChamfer(4,1,width/1000,math.radians(angle),0.,0.,0.,0.)
            doc.ClearSelection2(True)
            if not doc.ForceRebuild3(False):
                raise RuntimeError('Rebuild failed')
            after = swlib.total_volume(raw)
            if feat is None or after >= before-1e-6 or len(swlib.bodies(raw)) != n:
                raise RuntimeError('Chamfer verification failed')
        expected = swlib.total_volume(raw)
        swlib.save_native(doc)
    return expected-v0

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('files',nargs='*')
    ap.add_argument('--list',dest='list_file')
    ap.add_argument('--out',default='./sealed')
    ap.add_argument('--angle',type=float,default=15.)
    ap.add_argument('--width',type=float,default=1.5)
    args = ap.parse_args()
    if not math.isfinite(args.width) or not math.isfinite(args.angle) or args.width <= 0 or not 0<args.angle<90:
        ap.error('width > 0 and 0 < angle < 90 required')
    try:
        patterns = args.files[:]
        if args.list_file:
            patterns += [s.strip() for s in Path(args.list_file).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
        files = expand_inputs(patterns)
        destinations = plan_outputs(files,args.out)
    except (ValueError,OSError) as exc:
        ap.error(str(exc))
    sw = swlib.app()
    failed = 0
    for src,dst in zip(files,destinations):
        try:
            dv = process(sw,src,dst,args.angle,args.width)
            print('OK',dst,'delta volume mm3:',dv)
        except Exception as exc:
            failed += 1
            print('ERROR',src,exc)
    return int(failed > 0)

if __name__ == '__main__':
    sys.exit(main())
