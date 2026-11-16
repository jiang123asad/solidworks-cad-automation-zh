# -*- coding: utf-8 -*-
"""Cut an explicit end cone: single coaxial XYZ-aligned part, standard Chinese planes.
Width and half angle are user parameters; no silent width reduction.
Uses isolated copies, aggregate and local geometry checks, and disk-volume readback.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swlib

M = 1000.0
PLANE_BY_AXIS = {0: "前视基准面", 1: "前视基准面", 2: "上视基准面"}


def matches_end_cone(circles, idx, end_coord, radius, width, depth, end, tolerance=0.02):
    inward_end = end_coord + depth if end == 'lo' else end_coord - depth
    return (len(circles) >= 2
            and any(abs(c[idx]-end_coord)<tolerance and abs(c[6]-(radius-width))<tolerance for c in circles)
            and any(abs(c[idx]-inward_end)<tolerance and abs(c[6]-radius)<tolerance for c in circles)
            and abs(max(c[6] for c in circles)-min(c[6] for c in circles)-width)<tolerance
            and abs(max(c[idx] for c in circles)-min(c[idx] for c in circles)-depth)<tolerance)


def modify(raw, width, half_angle, end, plane_z_flip=True):
    doc = swlib.model(raw)
    sk, fm = doc.SketchManager, doc.FeatureManager
    body, nbody = swlib.main_body(raw)
    if body is None or nbody != 1:
        raise ValueError('Requires a single solid body')

    # Do not infer axis from longest bbox dimension (disc-shaped parts).
    ax = swlib.axial_axis(body)
    if ax is None:
        raise ValueError('No unambiguous XYZ-aligned rotational axis')
    idx, lo, hi = ax
    org = None
    # Confirm a single coaxial cylinder family, including small-radius parts.
    offsets = []
    for f in swlib.faces(body):
        c = swlib.cyl_of(f)
        if c:
            offsets.append(tuple(round(c[k],5) for k in range(3) if k != idx))
            org = c[:3]
    if len(set(offsets)) != 1:
        raise ValueError('Multiple cylinder axes: select target axis explicitly')
    # Existing mapping assumes front plane Z=0 / top plane Y=0.
    normal_idx = 1 if idx == 2 else 2
    if abs(org[normal_idx]) > 1e-5:
        raise ValueError('Axis is outside standard sketch plane; transform required')

    circ = []
    for e in swlib.edges(body):
        c = swlib.circle_of(e)
        if c and abs(c[3 + idx]) > 1 - 1e-6:
            circ.append((c[idx], c[6]))

    def end_radii(t):
        return sorted(set(round(r, 2) for pos, r in circ if abs(pos - t) < 0.01))

    cands = []
    for tag, t in ((end, lo if end == "lo" else hi),):
        rs = end_radii(t)
        if not rs:
            continue
        face_width = (max(rs) - min(rs)) if len(rs) >= 2 else 0.0
        cands.append((face_width, max(rs), tag, t, rs))
    if not cands:
        raise RuntimeError("无端面圆形边（悬挂环/异形端面通常属于这类，跳过）")
    cands.sort(key=lambda x: (x[0], x[1]), reverse=True)
    _face_w, R, tag, t_end, rs = cands[0]
    if R <= 2.0:
        raise RuntimeError("端面半径过小 R=%.1f" % R)

    W_eff = width
    if R <= width:
        raise ValueError('Radial width reaches the rotation axis')
    if len(rs) >= 2 and width >= rs[-1] - rs[-2]:
        raise ValueError('Specified width exceeds end annulus; no automatic shrinking')
    D_eff = W_eff / math.tan(math.radians(half_angle))
    if D_eff >= hi-lo:
        raise ValueError('Cone depth exceeds part axial extent')

    vol0 = swlib.total_volume(raw)

    # 3) 放大到端部再画草图（降低捕捉容差）
    lo3, hi3 = [0.0] * 3, [0.0] * 3
    for k in range(3):
        if k == idx:
            lo3[k], hi3[k] = (t_end - 8.0) / M, (t_end + 3.0) / M
        elif k == 0:
            lo3[k], hi3[k] = (org[k] - 3.0) / M, (org[k] + R + 3.0) / M
        else:
            lo3[k], hi3[k] = (org[k] - 3.0) / M, (org[k] + 3.0) / M
    doc.ClearSelection2(True)
    doc.ShowNamedView2("*Front" if idx != 2 else "*Top", 1 if idx != 2 else 5)
    doc.ViewZoomTo2(lo3[0], lo3[1], lo3[2], hi3[0], hi3[1], hi3[2])
    doc.ClearSelection2(True)

    plane = swlib.find_plane(doc, PLANE_BY_AXIS[idx])
    if plane is None:
        raise RuntimeError("找不到基准面 " + PLANE_BY_AXIS[idx])
    if not swlib.select(plane):
        raise RuntimeError('Failed to select sketch plane')
    sk.InsertSketch(True)
    previous_add_to_db = sk.AddToDB
    try:
        sk.AddToDB = True
        flip = -1.0 if (idx == 2 and plane_z_flip) else 1.0
    
        def pt(r, a):
            if idx == 0:
                return (a, org[1] + r)
            if idx == 1:
                return (org[0] + r, a)
            return (org[0] + r, flip * a)      # 上视基准面 Y 轴指向 -Z
    
        # lo 端锥深朝内是 +，hi 端朝内是 -
        a_in = (t_end + D_eff) if tag == "lo" else (t_end - D_eff)
        p1, p2, p3 = pt(R, t_end), pt(R - W_eff, t_end), pt(R, a_in)
        for a, b in ((p1, p2), (p2, p3), (p3, p1)):
            sk.CreateLine(a[0] / M, a[1] / M, 0, b[0] / M, b[1] / M, 0)
    
        if idx == 0:
            sk.CreateCenterLine(lo / M, org[1] / M, 0, hi / M, org[1] / M, 0)
        elif idx == 1:
            sk.CreateCenterLine(org[0] / M, lo / M, 0, org[0] / M, hi / M, 0)
        else:
            sk.CreateCenterLine(org[0] / M, flip * lo / M, 0,
                                org[0] / M, flip * hi / M, 0)
    finally:
        sk.AddToDB = previous_add_to_db
        sk.InsertSketch(True)

    # 4) 旋转切除
    s = swlib.last_sketch(doc)
    npts = 0
    try:
        isk = swlib.wrap(swlib.mod().ISketch, s.GetSpecificFeature2())
        npts = len(isk.GetSketchPoints2() or [])
    except Exception:
        pass
    doc.ClearSelection2(True)
    s.Select2(False, 0)                    # ★ mark 0
    ft = fm.FeatureRevolveCut2(
        2 * math.pi, False, 0.0, 0, 0,
        False,                             # ★ UseFeatScope = False
        True, False, False, False)
    doc.ClearSelection2(True)
    if not ft:
        raise RuntimeError("旋转切除失败(草图点%d, %s端 R%.1f 宽%.2f)" % (
            npts, tag, R, W_eff))

    # Local cone check plus aggregate material removal; disk volume rechecked by part_output.
    if not doc.ForceRebuild3(False):
        raise RuntimeError('Rebuild failed')
    local_cones = []
    for face in swlib.faces(swlib.main_body(raw)[0]):
        c = swlib.cone_of(face)
        if c and c[2] is not None and abs(c[2]-half_angle) < 0.1:
            circles = [cc for cc in (swlib.circle_of(e) for e in swlib.edges_of_face(face)) if cc]
            if matches_end_cone(circles,idx,t_end,R,W_eff,D_eff,end):
                local_cones.append(c)
    vol1 = swlib.total_volume(raw)
    expected_removed = math.pi*D_eff*(R*W_eff-W_eff**2/3)
    if (not local_cones or vol1 >= vol0 or len(swlib.bodies(raw)) != nbody
        or abs((vol0-vol1)-expected_removed) > max(0.1,expected_removed*0.02)):
        raise RuntimeError('Cone angle/position/width/depth/volume verification failed')
    swlib.save_native(doc)
    return 'OK %s end width %.3f half angle %.3f delta volume %.6f' % (end,W_eff,half_angle,vol1-vol0)


def main():
    import argparse
    from batch_support import expand_inputs,plan_outputs
    ap = argparse.ArgumentParser(description='Cut a specified end cone in an isolated part copy')
    ap.add_argument('outdir')
    ap.add_argument('files',nargs='+')
    ap.add_argument('--width',type=float,default=3.37)
    ap.add_argument('--half-angle',type=float,default=75.)
    ap.add_argument('--end',choices=('lo','hi'),required=True)
    args = ap.parse_args()
    if not math.isfinite(args.width) or not math.isfinite(args.half_angle) or args.width <= 0 or not 0<args.half_angle<90:
        ap.error('width > 0 and 0 < half-angle < 90 required')
    try:
        files = expand_inputs(args.files)
        outputs = plan_outputs(files,args.outdir)
    except (ValueError,OSError) as exc:
        ap.error(str(exc))
    sw = swlib.app()
    failed = 0
    for src,dst in zip(files,outputs):
        try:
            with swlib.part_output(sw,src,dst) as (raw,_staged):
                result = modify(raw,args.width,args.half_angle,args.end)
            print(result,dst)
        except Exception as exc:
            failed += 1
            print('ERROR',src,exc)
    return int(failed > 0)

if __name__ == '__main__':
    sys.exit(main())
