# -*- coding: utf-8 -*-
"""SolidWorks COM 早期绑定封装（pywin32）。

为什么需要这层封装：
SolidWorks 的 IDispatch 晚绑定（win32com.client.Dispatch）拿不到 IEdge / ICurve /
ISurface 的成员，调用 GetCurve() 会报「找不到成员」。必须用类型库生成早期绑定模块，
并把返回的子对象手动包成对应接口（IModelDoc2 / IBody2 / IEdge / ICurve / ISurface ...）。

典型用法：
    import swlib
    sw = swlib.app()
    raw = swlib.open_doc(sw, r"D:\\part.SLDPRT")
    doc = swlib.model(raw)
    body = swlib.bodies(raw)[0]
    for e in swlib.edges(body):
        c = swlib.circle_of(e)          # 圆形边 -> (cx,cy,cz,ax,ay,az,r) mm
"""
import glob
import os
import time
import warnings
from contextlib import contextmanager
from pathlib import Path

try:
    import pythoncom
    import win32com.client
    import win32com.client.gencache as gc
except ImportError:
    pythoncom = None
    gc = None

TLB = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
MOD = None


def _find_tlb():
    """定位 sldworks.tlb：优先注册表，其次常见安装路径。"""
    try:
        import winreg
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for flag in (winreg.KEY_READ, winreg.KEY_READ | winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(root, r"SOFTWARE\Classes\TypeLib" + "\\" + TLB, 0, flag) as key:
                        versions = []
                        for i in range(winreg.QueryInfoKey(key)[0]):
                            versions.append(winreg.EnumKey(key, i))
                        for version in sorted(versions, reverse=True):
                            with winreg.OpenKey(key, version) as vk:
                                for j in range(winreg.QueryInfoKey(vk)[0]):
                                    locale = winreg.EnumKey(vk, j)
                                    for arch in ('win64', 'win32'):
                                        try:
                                            with winreg.OpenKey(vk, locale + '\\' + arch) as ak:
                                                val, _ = winreg.QueryValueEx(ak, '')
                                                if val and os.path.isfile(val):
                                                    return val
                                        except OSError:
                                            continue
                except OSError:
                    pass
    except Exception:
        pass
    patterns = [
        r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\sldworks.tlb",
        r"D:\*\SOLIDWORKS\sldworks.tlb",
        r"C:\Program Files\*\SOLIDWORKS\sldworks.tlb",
    ]
    for pat in patterns:
        for hit in glob.glob(pat):
            return hit
    raise FileNotFoundError("找不到 sldworks.tlb，请设置环境变量 SLDWORKS_TLB")


def _tlb_path():
    env = os.environ.get("SLDWORKS_TLB")
    if env:
        if not os.path.isfile(env):
            raise FileNotFoundError('SLDWORKS_TLB does not name a file: ' + env)
        return env
    return _find_tlb()


def mod():
    global MOD
    if pythoncom is None:
        raise RuntimeError('Windows Python with pywin32 is required')
    if MOD is None:
        attr = pythoncom.LoadTypeLib(_tlb_path()).GetLibAttr()
        guid, lcid, major, minor = attr[0], attr[1], attr[3], attr[4]
        try:
            MOD = gc.EnsureModule(str(guid), lcid, major, minor)
        except Exception:
            MOD = None
        if MOD is None:
            # Some installations expose a file but lack a usable typelib registration.
            import win32com.client.makepy as makepy
            tlb = pythoncom.LoadTypeLib(_tlb_path())
            makepy.GenerateFromTypeLibSpec(tlb, bForDemand=False, bBuildHidden=1)
            MOD = gc.GetModuleForTypelib(str(guid), lcid, major, minor)
        if MOD is None:
            raise RuntimeError('Cannot generate SolidWorks type-library bindings')
    return MOD


def wrap(cls, obj):
    """把 IDispatch 包成类型库里的具体接口，例如 wrap(mod().IEdge, edge)。"""
    return cls(obj._oleobj_)


def app(visible=True, retries=30, delay=2.0):
    """连接（或启动）SolidWorks。刚启动时会有一段时间连不上，需要重试。"""
    if pythoncom is None:
        raise RuntimeError('Windows Python with pywin32 is required')
    pythoncom.CoInitialize()
    last = None
    for _ in range(retries):
        try:
            sw = mod().SldWorks()
            if visible:
                sw.Visible = True
            return sw
        except Exception as e:
            last = e
            time.sleep(delay)
    raise RuntimeError("连接 SolidWorks 失败: %s" % last)


def open_doc(sw, path, typ=None, silent=1, configuration='', readonly=False):
    """打开文档。typ: 1=零件 2=装配 3=工程图。

    注意：早期绑定下 OpenDoc6 返回 tuple (doc, errors, warnings)，必须取 [0]。
    """
    path = str(Path(path).resolve(strict=True))
    typ = typ or doc_type(path)
    res = sw.OpenDoc6(path, typ, int(silent) | (2 if readonly else 0), configuration, 0, 0)
    d = res[0] if isinstance(res, tuple) else res
    errors = res[1] if isinstance(res, tuple) and len(res) > 1 else 0
    warn = res[2] if isinstance(res, tuple) and len(res) > 2 else 0
    if warn:
        warnings.warn('OpenDoc6 warnings=%s: %s' % (warn, path))
    if d is None or errors:
        if d is not None:
            # owned_doc preflights ownership before calling this helper.
            warnings.warn('OpenDoc6 returned a document with errors; not auto-closing it')
        raise RuntimeError('OpenDoc6 errors=%s: %s' % (errors, path))
    return d


def doc_type(path):
    try:
        return {'.sldprt': 1, '.sldasm': 2, '.slddrw': 3}[Path(path).suffix.lower()]
    except KeyError:
        raise ValueError('Unsupported SolidWorks document: %s' % path)


@contextmanager
def owned_doc(sw, path, readonly=True):
    """Refuse pre-existing documents; close only the document opened here."""
    path = str(Path(path).resolve(strict=True))
    if sw.GetOpenDocumentByName(path) is not None:
        raise RuntimeError('File already open; use a saved, closed input copy: ' + path)
    raw = None
    try:
        raw = open_doc(sw, path, readonly=readonly)
        yield raw
    finally:
        # On OpenDoc6 errors it may still have opened a document.
        own = raw if raw is not None else sw.GetOpenDocumentByName(path)
        if own is not None:
            sw.CloseDoc(model(own).GetTitle())
            if sw.GetOpenDocumentByName(path) is not None:
                raise RuntimeError('Failed to close owned document: ' + path)


def _save_result(result, operation):
    ok = result[0] if isinstance(result, tuple) else result
    errors = result[1] if isinstance(result, tuple) and len(result) > 1 else 0
    warn = result[2] if isinstance(result, tuple) and len(result) > 2 else 0
    if warn:
        warnings.warn('%s warnings=%s' % (operation, warn))
    if not ok or errors:
        raise RuntimeError('%s failed: errors=%s warnings=%s' % (operation, errors, warn))


def save_native(doc):
    _save_result(doc.Save3(1, 0, 0), 'Save3')


def save_as(doc, path):
    path = str(Path(path).resolve())
    if Path(path).exists():
        raise FileExistsError(path)
    doc.ClearSelection2(True)
    _save_result(doc.Extension.SaveAs(path, 0, 1, None, 0, 0), 'Extension.SaveAs')
    if not Path(path).is_file() or Path(path).stat().st_size == 0:
        raise RuntimeError('Save returned success but file missing/empty: ' + path)


@contextmanager
def part_output(sw, source, destination):
    from batch_support import staged_file
    if sw.GetOpenDocumentByName(str(Path(source).resolve(strict=True))) is not None:
        raise RuntimeError('Source already open; use a saved, closed input copy: ' + str(source))
    previous_dir = sw.GetCurrentWorkingDirectory()
    with staged_file(destination, source) as staged:
        try:
            with owned_doc(sw, staged, readonly=False) as raw:
                yield raw, str(staged)
                expected = total_volume(raw)
            verify_volume_file(sw, staged, expected)
        finally:
            if not sw.SetCurrentWorkingDirectory(previous_dir):
                warnings.warn('Could not restore SolidWorks working directory: ' + previous_dir)


def verify_volume_file(sw, path, expected):
    with owned_doc(sw, path) as raw:
        actual = total_volume(raw)
        if abs(actual - expected) > max(1e-4, abs(expected) * 1e-7):
            raise RuntimeError('Saved volume differs: %g vs %g mm3' % (actual, expected))


def model(doc_raw):
    return wrap(mod().IModelDoc2, doc_raw)


def bodies(doc_raw):
    """取实体。GetBodies2 在 IPartDoc 上，不在 IModelDoc2。"""
    if model(doc_raw).GetType() != 1:
        raise ValueError('Solid-body geometry helpers support SLDPRT only')
    p = wrap(mod().IPartDoc, doc_raw)
    return [wrap(mod().IBody2, b) for b in (p.GetBodies2(0, False) or [])]


def edges(body):
    return [wrap(mod().IEdge, e) for e in (body.GetEdges() or [])]


def faces(body):
    return [wrap(mod().IFace2, f) for f in (body.GetFaces() or [])]


def circle_of(edge):
    """圆形边 -> (cx, cy, cz, ax, ay, az, r)，单位 mm；不是圆返回 None。"""
    c = edge.GetCurve()
    if c is None:
        return None
    c = wrap(mod().ICurve, c)
    try:
        if not c.IsCircle():
            return None
    except Exception:
        return None
    vals = list(c.GetCircleParams2() if hasattr(c, "GetCircleParams2") else c.CircleParams)
    cx, cy, cz, ax, ay, az, r = vals[:7]
    return (cx * 1000, cy * 1000, cz * 1000, ax, ay, az, r * 1000)


def cyl_of(face):
    """圆柱面 -> [ox,oy,oz,ax,ay,az,r]，单位 mm；不是圆柱返回 None。"""
    s = face.GetSurface()
    if s is None:
        return None
    s = wrap(mod().ISurface, s)
    try:
        if not s.IsCylinder():
            return None
    except Exception:
        return None
    vals = list(s.CylinderParams if hasattr(s, "CylinderParams") else s.GetCylinderParams2())
    return [v * 1000 for v in vals[:3]] + vals[3:6] + [vals[6] * 1000]


def cone_of(face):
    """锥面 -> (origin xyz mm, axis xyz, 半角 deg, 基准圆半径 mm)；不是锥面返回 None。"""
    import math
    s = face.GetSurface()
    if s is None:
        return None
    s = wrap(mod().ISurface, s)
    try:
        if not s.IsCone():
            return None
    except Exception:
        return None
    v = list(s.ConeParams)
    return ([x * 1000 for x in v[:3]], list(v[3:6]),
            math.degrees(v[7]) if len(v) > 7 else None, v[6] * 1000)


def new_part(sw, retries=1, delay=2.0):
    """Create once by default; requires a configured default part template."""
    last = None
    for _ in range(retries):
        try:
            d = sw.NewPart()
            if d is not None:
                return d
        except Exception as e:
            last = e
        time.sleep(delay)
    raise RuntimeError("新建零件失败: %s" % last)


def select(obj, append=False):
    """选实体：先试 Select2，失败再试 Select4。"""
    ent = wrap(mod().IEntity, obj)
    for fn, args in (("Select2", (append, 0)), ("Select4", (append, None))):
        try:
            if getattr(ent, fn)(*args):
                return True
        except Exception:
            continue
    return False


def select_mark(doc_raw, entity, mark, append=True):
    """带 Mark 选面/边等 IEntity；IBody2 使用 select_body_mark。

    来自 wzyn20051216/solidworks-automation-skill 的做法。
    """
    mgr = wrap(mod().ISelectionMgr, doc_raw.SelectionManager)
    data = mgr.CreateSelectData()
    data.Mark = int(mark)
    return bool(wrap(mod().IEntity, entity).Select4(append, data))


def select_body_mark(doc_raw, body, mark, append=False):
    """IBody2 不提供 IEntity.Select4；用原生 Select2 和 SelectData.Mark。"""
    mgr = wrap(mod().ISelectionMgr, model(doc_raw).SelectionManager)
    data = mgr.CreateSelectData()
    data.Mark = int(mark)
    return bool(wrap(mod().IBody2, body).Select2(append, data))


def walk_features(doc, out=None, limit=4000):
    """递归遍历特征树，返回 [(类型, 名称, 层级), ...]。

    子特征链必须用 GetNextSubFeature()。用 GetNextFeature() 会越界走出子链，
    在复杂零件上会死循环 —— 这是装饰螺纹、孔底倒角这类子特征漏检的根因。
    """
    if out is None:
        out = []

    def _sub(first, depth):
        if depth > 64:
            raise RuntimeError('Feature tree exceeds maximum depth (64)')
        f, guard = first, 0
        while f is not None and guard < limit:
            if len(out) >= limit:
                raise RuntimeError('Feature tree exceeds node budget (%d)' % limit)
            guard += 1
            ff = wrap(mod().IFeature, f)
            try:
                out.append((ff.GetTypeName2(), ff.Name, depth))
            except Exception:
                return
            try:
                s = ff.GetFirstSubFeature()
            except Exception:
                s = None
            if s is not None:
                _sub(s, depth + 1)
            try:
                f = ff.GetNextSubFeature()
            except Exception:
                return

    f, guard = doc.FirstFeature(), 0
    while f is not None and guard < limit:
        if len(out) >= limit:
            raise RuntimeError('Feature tree exceeds node budget (%d)' % limit)
        guard += 1
        ff = wrap(mod().IFeature, f)
        try:
            out.append((ff.GetTypeName2(), ff.Name, 0))
        except Exception:
            break
        try:
            s = ff.GetFirstSubFeature()
        except Exception:
            s = None
        if s is not None:
            _sub(s, 1)
        try:
            f = ff.GetNextFeature()
        except Exception:
            break
    if f is not None:
        raise RuntimeError('Feature tree exceeds node budget (%d)' % limit)
    return out


def find_feature(doc, name):
    """按名称取特征（仅顶层）。"""
    f = doc.FirstFeature()
    while f is not None:
        f = wrap(mod().IFeature, f)
        if f.Name == name:
            return f
        f = f.GetNextFeature()
    return None


def last_sketch(doc):
    """取最后一个草图特征（配合草图操作后选择轮廓用）。"""
    f = doc.FirstFeature()
    last = None
    while f is not None:
        f = wrap(mod().IFeature, f)
        if f.GetTypeName2() == "ProfileFeature":
            last = f
        f = f.GetNextFeature()
    return last


def find_plane(doc, name="前视基准面"):
    """按名字找基准面。中文界面为「前视/上视/右视基准面」。"""
    f = doc.FirstFeature()
    while f is not None:
        f = wrap(mod().IFeature, f)
        if f.GetTypeName2() == "RefPlane" and f.Name == name:
            return f
        f = f.GetNextFeature()
    return None


def edges_of_face(face):
    """面上的边。用于把锥面半角与端面半径关联起来验证。"""
    return [wrap(mod().IEdge, e) for e in (face.GetEdges() or [])]


def plane_face_at(raw, axis, coord, tol=0.5):
    """找法向沿 axis、坐标等于 coord(mm) 的平面。抽壳前选要移除的面常用。

    axis: 0=X 1=Y 2=Z。判据是该面在 axis 方向的包围盒厚度 < 0.3mm。
    """
    M = mod()
    for b in bodies(raw):
        for f in faces(b):
            s = f.GetSurface()
            if s is None:
                continue
            s = wrap(M.ISurface, s)
            try:
                if not s.IsPlane():
                    continue
            except Exception:
                continue
            fb = [v * 1000 for v in f.GetBox()]
            if abs(fb[axis] - fb[axis + 3]) < 0.3 and abs(fb[axis] - coord) < tol:
                return f
    return None


def main_body(raw):
    """多实体零件取体积最大的主体，返回 (body, 实体数)。

    多实体零件只看 bodies[0] 会误判（见 api-pitfalls.md 第 14/20 节）。
    """
    bs = bodies(raw)
    best, vol = None, -1.0
    for b in bs:
        try:
            v = b.GetMassProperties(1)[3]
        except Exception:
            v = 0.0
        if v > vol:
            best, vol = b, v
    return best, len(bs)


def total_volume(raw):
    """所有实体的体积总和 mm³ —— 版本对比 / 特征验证要用这个，不要用单实体。"""
    return sum(b.GetMassProperties(1)[3] * 1e9 for b in bodies(raw))


def total_faces(raw):
    """所有实体的面数总和。"""
    return sum(len(faces(b)) for b in bodies(raw))


def axial_axis(body):
    """推断回转体的轴向：返回 (轴索引 0/1/2, 最小坐标 mm, 最大坐标 mm)。"""
    from collections import Counter
    cnt = Counter()
    offsets = set()
    for f in faces(body):
        p = cyl_of(f)
        if p:
            axis = list(p[3:6])
            norm = sum(v*v for v in axis) ** 0.5
            if not norm:
                return None
            axis = [abs(v / norm) for v in axis]
            idx = axis.index(max(axis))
            if axis[idx] < 1 - 1e-6:
                return None
            key = tuple(1 if k == idx else 0 for k in range(3))
            cnt[key] += 1
            offsets.add(tuple(round(p[k], 5) for k in range(3) if k != idx))
    if not cnt:
        return None
    if len(cnt) != 1 or len(offsets) != 1:
        return None
    key = next(iter(cnt))
    idx = list(key).index(max(key))
    vals = []
    axis_offset = next(iter(offsets))
    for e in edges(body):
        c = circle_of(e)
        if (c and abs(c[3 + idx]) > 1 - 1e-6
                and tuple(round(c[k], 5) for k in range(3) if k != idx) == axis_offset):
            vals.append((c[0], c[1], c[2])[idx])
    if not vals:
        return None
    return idx, min(vals), max(vals)


def volume(body):
    """实体体积，单位 mm³。"""
    return body.GetMassProperties(1)[3] * 1e9


def save_bmp(doc, path, w=1600, h=1100):
    """渲染存图。SaveBMP 必须传绝对路径，扩展名必须是 .bmp。"""
    import tempfile
    from PIL import Image
    path = Path(path).resolve()
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.sw-image-', dir=path.parent) as tmp:
        bmp = str(Path(tmp) / 'view.bmp')
        if not doc.SaveBMP(bmp, w, h) or not Path(bmp).is_file():
            raise RuntimeError('SaveBMP failed')
        with Image.open(bmp) as im:
            im.save(str(path))
    return str(path)
