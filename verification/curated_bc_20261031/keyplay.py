#!/usr/bin/env python3
"""Focus the Wesnoth window on $DISPLAY and press one key repeatedly."""
import ctypes
import ctypes.util
import os
import signal
import sys
import time

keysym_text = (sys.argv[1] if len(sys.argv) > 1 else 'p').encode()
interval = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 600

x11 = ctypes.CDLL(ctypes.util.find_library('X11') or 'libX11.so.6')
xtst = ctypes.CDLL(ctypes.util.find_library('Xtst') or 'libXtst.so.6')

x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XDefaultRootWindow.restype = ctypes.c_ulong
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XQueryTree.restype = ctypes.c_int
x11.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                           ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
                           ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)), ctypes.POINTER(ctypes.c_uint)]
x11.XGetGeometry.restype = ctypes.c_int
x11.XGetGeometry.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                             ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
                             ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint),
                             ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
                             ctypes.POINTER(ctypes.c_uint)]
x11.XSetInputFocus.restype = ctypes.c_int
x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
x11.XStringToKeysym.restype = ctypes.c_ulong
x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
x11.XKeysymToKeycode.restype = ctypes.c_ubyte
x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
x11.XFlush.restype = ctypes.c_int
x11.XFlush.argtypes = [ctypes.c_void_p]
x11.XFree.argtypes = [ctypes.c_void_p]
xtst.XTestFakeKeyEvent.restype = ctypes.c_int
xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]


def stop(*_):
    sys.exit(0)


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

display = x11.XOpenDisplay(None)
if not display:
    raise SystemExit('cannot open display %r' % os.environ.get('DISPLAY'))
root = x11.XDefaultRootWindow(display)
keycode = x11.XKeysymToKeycode(display, x11.XStringToKeysym(keysym_text))


def big_child():
    root_return = ctypes.c_ulong()
    parent_return = ctypes.c_ulong()
    children = ctypes.POINTER(ctypes.c_ulong)()
    count = ctypes.c_uint()
    if not x11.XQueryTree(display, root, ctypes.byref(root_return), ctypes.byref(parent_return),
                          ctypes.byref(children), ctypes.byref(count)):
        return 0
    best = (0, 0)
    for index in range(count.value):
        window = children[index]
        geometry_root = ctypes.c_ulong()
        x = ctypes.c_int()
        y = ctypes.c_int()
        width = ctypes.c_uint()
        height = ctypes.c_uint()
        border = ctypes.c_uint()
        depth = ctypes.c_uint()
        if x11.XGetGeometry(display, window, ctypes.byref(geometry_root), ctypes.byref(x), ctypes.byref(y),
                            ctypes.byref(width), ctypes.byref(height), ctypes.byref(border), ctypes.byref(depth)):
            area = width.value * height.value
            if area > best[1]:
                best = (window, area)
    if children:
        x11.XFree(children)
    return best[0]


for _ in range(rounds):
    window = big_child()
    if window and keycode:
        x11.XSetInputFocus(display, window, 2, 0)
        xtst.XTestFakeKeyEvent(display, keycode, 1, 0)
        xtst.XTestFakeKeyEvent(display, keycode, 0, 0)
        x11.XFlush(display)
        print('sent %s to 0x%x' % (keysym_text.decode(), window), flush=True)
    else:
        print('no window yet', flush=True)
    time.sleep(interval)
