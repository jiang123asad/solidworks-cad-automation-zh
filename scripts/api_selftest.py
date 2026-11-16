# -*- coding: utf-8 -*-
"""新机器 / 新 SolidWorks 版本的 API 能力自检。

会新建一个临时零件做特征测试，**不改动任何现有文件**，结束后关闭文档。
不会调用已知会让 SW 崩溃的 FeatureLinearPattern4。

用法:
    python api_selftest.py                 # 特征冒烟自检
    python api_selftest.py --quick         # 只测连接、绑定与新建
    python api_selftest.py --keep out.SLDPRT   # 顺便把测试零件存下来看

输出每项 PASS / FAIL / SKIP。换 SW 版本后务必重跑一次，不要照搬本包的
「可用 / 不可用」结论 —— 那些都是 SW2026 实测结果。
"""
import argparse
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swlib

M = 1000.0
RESULTS = []
CREATED = []


def rec(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print('%-6s %-34s %s' % ('PASS' if ok else 'FAIL', name, detail))


def skip(name, why):
    RESULTS.append((name, None, why))
    print('%-6s %-34s %s' % ('SKIP', name, why))


def new_doc(sw):
    raw = swlib.new_part(sw)
    CREATED.append(raw)
    return raw, swlib.model(raw)


def sketch_on(doc, plane='前视基准面'):
    sk = doc.SketchManager
    doc.ClearSelection2(True)
    p = swlib.find_plane(doc, plane)
    if p is None:
        raise RuntimeError('找不到基准面 %s' % plane)
    swlib.select(p)
    sk.InsertSketch(True)
    try:
        sk.AddToDB = True
    except Exception:
        pass
    return sk


def close_sk(sk):
    try:
        sk.AddToDB = False
    except Exception:
        pass
    sk.InsertSketch(True)


def do_extrude(doc, h, both=False):
    s = swlib.last_sketch(doc)
    doc.ClearSelection2(True)
    s.Select2(False, 0)
    r = doc.FeatureManager.FeatureExtrusion2(
        True, False, both, 0, 0, h, 0.0,
        False, False, False, False, 0, 0,
        False, False, False, False, True, True, True, 0, 0, False)
    doc.ClearSelection2(True)
    doc.ForceRebuild3(False)
    return r


def do_cut(doc, depth, draft_deg=0.0):
    s = swlib.last_sketch(doc)
    doc.ClearSelection2(True)
    s.Select2(False, 0)
    r = doc.FeatureManager.FeatureCut4(
        True, False, True, 0, 0, depth, 0.0,
        bool(draft_deg), False, False, False,
        math.radians(draft_deg), 0.0,
        False, False, False, False, False, True, True, False, False, False,
        0, 0.0, False, True)
    doc.ClearSelection2(True)
    doc.ForceRebuild3(False)
    return r


def vol(raw):
    return swlib.total_volume(raw)


def check_binding(sw):
    try:
        m = swlib.mod()
        rec('早期绑定 / 类型库', True, str(m.__name__)[:40])
    except Exception as e:
        rec('早期绑定 / 类型库', False, str(e)[:70])
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--keep', default=None)
    args = ap.parse_args()

    RESULTS.clear()
    CREATED.clear()
    if args.keep and os.path.exists(args.keep):
        ap.error('Keep path already exists')
    print('连接 SolidWorks ...')
    try:
        sw = swlib.app()
    except Exception as e:
        print('连接失败:', e)
        return 1
    rec('连接 SolidWorks', True)
    if not check_binding(sw):
        return 1

    try:
        raw, doc = new_doc(sw)
        rec('NewPart 新建零件', raw is not None)
        if args.quick:
            _finish(sw, raw, args.keep)
            return int(any(ok is False for _,ok,_ in RESULTS))
    
        # --- 草图 ---
        sk = sketch_on(doc)
        try:
            sk.CreateLine(0, 0, 0, 0.05, 0, 0)
            sk.CreateCircleByRadius(0.025, 0.025, 0, 0.01)
            try:
                segment = sk.CreateArc(0.01, 0.01, 0, 0.02, 0.01, 0, 0.01, 0.02, 0, 1)
                arc = segment is not None
            except Exception as exc:
                arc = False
                print('CreateArc error:', exc)
            sk.CreateCenterLine(0, -0.01, 0, 0, 0.06, 0)
            close_sk(sk)
            rec('草图 直线/圆/中心线', True)
            rec('ISketchManager.CreateArc 圆弧', arc, '按当前类型库的 10 参数签名调用')
        except Exception as e:
            rec('草图 直线/圆/中心线', False, str(e)[:70])
    
        # --- 拉伸凸台（用干净的矩形草图） ---
        raw, doc = new_doc(sw)
        sk = sketch_on(doc)
        sk.CreateCornerRectangle(0, 0, 0, 0.06, 0.06, 0)
        close_sk(sk)
        v0 = 0.0
        try:
            r = do_extrude(doc, 0.02)
            v1 = vol(raw)
            rec('FeatureExtrusion2 拉伸凸台', r is not None and v1 > 0,
                '体积 %.0f mm3' % v1)
            v0 = v1
        except Exception as e:
            rec('FeatureExtrusion2 拉伸凸台', False, str(e)[:70])
    
        # --- 拉伸切除（Dir=True）+ 拔模 ---
        if v0 > 0:
            sk = sketch_on(doc)
            sk.CreateCircleByRadius(0.03, 0.03, 0, 0.008)
            close_sk(sk)
            try:
                r = do_cut(doc, 0.03, draft_deg=10.0)
                v2 = vol(raw)
                rec('FeatureCut4 切除 + 10° 拔模', r is not None and v2 < v0,
                    'ΔV %.0f mm3' % (v2 - v0))
            except Exception as e:
                rec('FeatureCut4 切除 + 10° 拔模', False, str(e)[:70])
    
            # --- 抽壳 ---
            try:
                f = swlib.plane_face_at(raw, 1, 60.0)
                if f:
                    doc.ClearSelection2(True)
                    swlib.select(f)
                    vb = vol(raw)
                    doc.InsertFeatureShell(0.002, False)
                    doc.ClearSelection2(True)
                    doc.ForceRebuild3(False)
                    va = vol(raw)
                    rec('InsertFeatureShell 抽壳', va < vb, 'ΔV %.0f mm3' % (va - vb))
                else:
                    rec('InsertFeatureShell 抽壳', False, '找不到 Y=60 平面')
            except Exception as e:
                rec('InsertFeatureShell 抽壳', False, str(e)[:70])
    
        # --- 旋转切除（闭合三角形 + AddToDB + UseFeatScope=False + mark 0） ---
        raw, doc = new_doc(sw)
        sk = sketch_on(doc)
        sk.CreateCornerRectangle(0, 0, 0, 0.06, 0.06, 0)
        close_sk(sk)
        do_extrude(doc, 0.04)
        v0 = vol(raw)
        try:
            sk = sketch_on(doc)
            W, D = 3.0, 3.0 * math.tan(math.radians(15.0))
            pts = [(30.0, 40.0), (30.0 - W, 40.0), (30.0, 40.0 - D)]
            for a, b in ((pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[0])):
                sk.CreateLine(a[0] / M, a[1] / M, 0, b[0] / M, b[1] / M, 0)
            sk.CreateCenterLine(30 / M, 0, 0, 30 / M, 50 / M, 0)
            close_sk(sk)
            s = swlib.last_sketch(doc)
            npts = 0
            try:
                isk = swlib.wrap(swlib.mod().ISketch, s.GetSpecificFeature2())
                npts = len(isk.GetSketchPoints2() or [])
            except Exception:
                pass
            doc.ClearSelection2(True)
            s.Select2(False, 0)
            r = doc.FeatureManager.FeatureRevolveCut2(
                2 * math.pi, False, 0.0, 0, 0, False, True, False, False, False)
            doc.ClearSelection2(True)
            doc.ForceRebuild3(False)
            v1 = vol(raw)
            rec('FeatureRevolveCut2 旋转切除', r is not None and v1 < v0,
                '草图点 %d（应为 5）, ΔV %.0f mm3' % (npts, v1 - v0))
        except Exception as e:
            rec('FeatureRevolveCut2 旋转切除', False, str(e)[:70])
    
        # --- 已知不可用 / 危险项，只记录不硬闯 ---
        skip('FeatureLinearPattern4', '原包用例曾崩溃，此冒烟测试不重放')
        skip('FeatureCircularPattern4 / 镜像', '历史用例未调通，本测试不覆盖；可用 GUI，见 gui-and-tooling.md')
        skip('独立拔模特征 / 筋 / 异型孔', '当前示例未覆盖；不表示无 API；内建拔模参数已在上文测过')
    
        # --- 读几何 / 导出 ---
        try:
            feats = swlib.walk_features(doc)
            rec('walk_features 递归特征树', len(feats) > 2, '%d 个节点' % len(feats))
            rec('读体积/面数', vol(raw) > 0, '%.0f mm3 / %d 面' %
                (vol(raw), swlib.total_faces(raw)))
        except Exception as e:
            rec('读体积/面数', False, str(e)[:70])
    
        _finish(sw, raw, args.keep)
        return int(any(ok is False for _,ok,_ in RESULTS))
    finally:
        for owned in CREATED:
            try:
                sw.CloseDoc(swlib.model(owned).GetTitle())
            except Exception as exc:
                print('Owned test document cleanup failed:',exc)



def _finish(sw, raw, keep):
    n_pass = sum(1 for _n, ok, _d in RESULTS if ok is True)
    n_fail = sum(1 for _n, ok, _d in RESULTS if ok is False)
    n_skip = sum(1 for _n, ok, _d in RESULTS if ok is None)
    print('\n汇总: PASS %d / FAIL %d / SKIP %d' % (n_pass, n_fail, n_skip))
    print('说明: FAIL 不一定是「功能不存在」，先按 SKILL.md「验证与故障处理」排查'
          '参数 / 接口归属 / 几何前置条件，再考虑切 GUI。')
    if keep:
        p = os.path.abspath(keep)
        os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
        try:
            swlib.save_as(swlib.model(raw), p)
            print('测试零件已存:', p)
        except Exception as e:
            rec('Save test part', False, str(e))


if __name__ == '__main__':
    sys.exit(main())

