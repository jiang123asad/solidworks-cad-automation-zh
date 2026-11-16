# -*- coding: utf-8 -*-
"""Legacy Win32 helper; use only where host permits direct desktop input.
Verify current screenshot, coordinate mapping, window focus and candidate buttons.
confirm/cancel only locate candidates by default; explicitly opt into a click
after observing that the candidate is the intended control.
"""
import time
from pathlib import Path

import numpy as np
import win32api
import win32con
import win32gui
from PIL import ImageGrab

VK_MENU = 0x12
VK_CONTROL = 0x11
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002

# 常用菜单助记符（按菜单上括号里的字母，不是拼音首字母）
MNEMONIC = {
    'I': 0x49,   # 插入
    'E': 0x45,   # 阵列/镜像
    'L': 0x4C,   # 线性阵列
    'C': 0x43,   # 圆周阵列
    'M': 0x4D,   # 镜向
    'F': 0x46,   # 特征
    'S': 0x53,   # 曲面
}


def focus_sw():
    """把 SolidWorks 窗口最大化并置前。截图前必调，否则会抓到别的窗口。"""
    res = []
    win32gui.EnumWindows(
        lambda h, _: res.append(h)
        if win32gui.IsWindowVisible(h) and 'SOLIDWORKS' in win32gui.GetWindowText(h).upper()
        else None, None)
    if len(res) != 1:
        raise RuntimeError('Expected exactly one visible SolidWorks window')
    try:
        win32gui.ShowWindow(res[0], win32con.SW_MAXIMIZE)
        win32gui.SetForegroundWindow(res[0])
    except Exception:
        pass
    time.sleep(0.5)
    if win32gui.GetForegroundWindow() != res[0]:
        raise RuntimeError('SolidWorks did not become foreground')
    return res[0]


def shot(path=None):
    """截全屏，返回 PIL Image；给了路径就顺手存盘。"""
    im = ImageGrab.grab()
    if path:
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        im.save(path)
    return im


def find_button(im, color='green', region=(0, 80, 120, 500)):
    """在左侧面板区域找绿色(确定)或红色(取消)按钮。

    返回 (cx, cy, 像素数) 或 None。像素数 < 25 视为面板里其它小图标的误判。
    """
    x0, y0, x1, y1 = region
    a = np.array(im.crop((x0, y0, x1, y1)).convert('RGB')).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    if color == 'green':
        mask = (g > 90) & (g < 190) & (r < 110) & (b < 130) & (g - r > 40)
    else:
        mask = (r > 120) & (g < 110) & (b < 110) & (r - g > 50)
    ys, xs = np.where(mask)
    if len(xs) < 25:
        return None
    # Connected components: never take a median across separated green objects.
    pending = set(zip(ys.tolist(),xs.tolist()))
    groups = []
    while pending:
        seed = pending.pop()
        stack,group = [seed],[seed]
        while stack:
            y,x = stack.pop()
            for q in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                if q in pending:
                    pending.remove(q)
                    stack.append(q)
                    group.append(q)
        if len(group) >= 25:
            groups.append(group)
    if len(groups) != 1:
        return None
    cy,cx = groups[0][len(groups[0])//2]
    return cx+x0,cy+y0,len(groups[0])


def click(x, y, wait=0.6):
    win32api.SetCursorPos((int(x), int(y)))
    time.sleep(0.15)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.07)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(wait)


def dclick(x, y, wait=0.5):
    """面板输入框单击只聚焦，输入不进去 —— 必须双击。"""
    click(x, y, 0.15)
    click(x, y, wait)


def key(vk, wait=0.2):
    win32api.keybd_event(vk, 0, 0, 0)
    time.sleep(0.04)
    win32api.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(wait)


def alt_menu_then(vks, gap=0.8):
    """菜单导航的唯一可靠姿势：Alt 单独按下松开 → 逐个按助记符。

    例: alt_menu_then([0x49, 0x45, 0x4C])   # 插入 → 阵列/镜像 → 线性阵列
        alt_menu_then('IEL')               # 等价写法
    """
    if isinstance(vks, str):
        vks = [MNEMONIC.get(ch.upper(), ord(ch.upper())) for ch in vks]
    win32api.keybd_event(VK_MENU, 0, 0, 0)
    time.sleep(0.12)
    win32api.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)   # ← 松开 Alt 再按字母
    time.sleep(0.5)
    for vk in vks:
        key(vk, gap)


def alt_key(vk, wait=0.9):
    """兼容旧调用名。内部已改为「Alt 分开按」，不再是 Alt+字母同时按。"""
    alt_menu_then([vk], gap=wait)


def type_number(n, wait=0.5):
    """在当前聚焦输入框里输入数值（整数/小数/负号）。前面必须已双击激活。"""
    win32api.keybd_event(VK_CONTROL, 0, 0, 0)
    key(0x41)                                  # Ctrl+A
    win32api.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.15)
    for ch in str(n):
        if ch.isdigit():
            key(0x30 + int(ch), 0.06)
        elif ch == '.':
            key(0xBE, 0.06)                    # VK_OEM_PERIOD
        elif ch == '-':
            key(0xBD, 0.06)                    # VK_OEM_MINUS
    time.sleep(wait)


def activate_panel(x=60, y=65):
    """面板打开后先点标题区激活焦点，否则点绿 ✓ 无效。"""
    click(x, y, 0.3)


def confirm(im=None, path='out/gui_confirm.png', click_candidate=False):
    """截图 → 找绿 ✓ → 点它。返回 (是否成功, 坐标)。"""
    im = im if im is not None else shot(path)
    pos = find_button(im, 'green')
    if not pos:
        return False, None
    if not click_candidate:
        return False, pos
    click(pos[0], pos[1], 2.2)
    return True, pos


def cancel(im=None, path='out/gui_cancel.png', click_candidate=False):
    im = im if im is not None else shot(path)
    pos = find_button(im, 'red')
    if not pos:
        return False, None
    if not click_candidate:
        return False, pos
    click(pos[0], pos[1], 0.8)
    return True, pos


def confirm_with_enter():
    """绿 ✓ 点不动时补一个回车，更稳。"""
    key(VK_RETURN, 0.8)


# ---------------------------------------------------------------------------
# 典型用法：API 预选 + 键盘开菜单 + 鼠标面板 + API 回读验证
# ---------------------------------------------------------------------------
EXAMPLE = '''
import swlib, gui_helper as gui

sw  = swlib.app()
raw = sw.ActiveDoc
doc = swlib.model(raw)

# 1) API 预选：种子特征 mark 4，轴 mark 1
doc.ClearSelection2(True)
seed.Select2(False, 4)
doc.Extension.SelectByID2(axis.Name, 'AXIS', 0, 0, 0, True, 1, None, 0)

# 2) 键盘：插入 → 阵列/镜像 → 圆周阵列
gui.focus_sw()
gui.alt_menu_then('IEC')
gui.activate_panel()                 # 必须先激活焦点

# 3) 鼠标：双击实例数输入框 → Ctrl+A → 输 6
gui.dclick(box_x, box_y)
gui.type_number(6)

# 4) 鼠标：按颜色定位绿 ✓
gui.confirm()

# 5) API 回读：体积/面数必须变化，否则特征无效
doc.ForceRebuild3(False)
print(swlib.total_volume(raw), swlib.total_faces(raw))
'''
