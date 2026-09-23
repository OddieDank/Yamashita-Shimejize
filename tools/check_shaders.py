#!/usr/bin/env python3
"""Compile/link expanded shader pairs with Mesa's surfaceless OpenGL context.

This checks GLSL, not Iris's Java transformer or Minecraft rendering. Iris-supplied
DH attributes/macros are stubbed, and uniforms are hoisted as Iris does.
"""
import ctypes as C
import os
from pathlib import Path
import re
import sys

os.environ.setdefault("EGL_PLATFORM", "surfaceless")
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
ROOT = Path(__file__).resolve().parents[1] / "shaders"
egl = C.CDLL("libEGL.so.1")
gl = C.CDLL("libGL.so.1")


def bind(lib, name, result, *args):
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = result, args
    return fn


ptr, integer, uint = C.c_void_p, C.c_int, C.c_uint
display = bind(egl, "eglGetDisplay", ptr, ptr)(None)
assert bind(egl, "eglInitialize", uint, ptr, ptr, ptr)(display, None, None), "EGL initialization failed"
assert bind(egl, "eglBindAPI", uint, uint)(0x30A2)
attrs = (integer * 7)(0x3033, 1, 0x3040, 8, 0x3024, 8, 0x3038)
config, count = ptr(), integer()
assert bind(egl, "eglChooseConfig", uint, ptr, ptr, ptr, integer, ptr)(display, attrs, C.byref(config), 1, C.byref(count)) and count.value
ctx_attrs = (integer * 7)(0x3098, 3, 0x30FB, 3, 0x30FD, 2, 0x3038)
context = bind(egl, "eglCreateContext", ptr, ptr, ptr, ptr, ptr)(display, config, None, ctx_attrs)
assert context and bind(egl, "eglMakeCurrent", uint, ptr, ptr, ptr, ptr)(display, None, None, context)
print(bind(gl, "glGetString", C.c_char_p, uint)(0x1F02).decode())
create_shader = bind(gl, "glCreateShader", uint, uint)
source_shader = bind(gl, "glShaderSource", None, uint, integer, ptr, ptr)
compile_shader = bind(gl, "glCompileShader", None, uint)
get_shader = bind(gl, "glGetShaderiv", None, uint, uint, ptr)
log_shader = bind(gl, "glGetShaderInfoLog", None, uint, integer, ptr, ptr)
create_program = bind(gl, "glCreateProgram", uint)
attach = bind(gl, "glAttachShader", None, uint, uint)
link = bind(gl, "glLinkProgram", None, uint)
get_program = bind(gl, "glGetProgramiv", None, uint, uint, ptr)
log_program = bind(gl, "glGetProgramInfoLog", None, uint, integer, ptr, ptr)
delete_shader = bind(gl, "glDeleteShader", None, uint)
delete_program = bind(gl, "glDeleteProgram", None, uint)


def expand(path, stack=()):
    assert path not in stack, f"Include cycle: {path}"
    def include(m):
        name = m[1]
        child = ROOT / name.lstrip("/") if name.startswith("/") else path.parent / name
        return expand(child, (*stack, path))
    return re.sub(r'^\s*#include\s+"([^"]+)".*$', include, path.read_text(), flags=re.M)


def prepare(path, dh, options):
    src = expand(path)
    for key, value in options.items():
        src = re.sub(rf'(#define {key})\s+[^\n]+', rf'\g<1> {value}', src)
    # GLSL 120 packs are upgraded by Iris. Keep compatibility built-ins available.
    version = re.search(r'#version[^\n]+', src)[0]
    src = src.replace('__VERSION__', version.split()[1])
    src = '#version 330 compatibility\n' + src.replace(version, '', 1)
    version = '#version 330 compatibility'
    defines = '#define MC_VERSION 260200\n#define IS_IRIS\n#define IRIS_VERSION 11104\n#define MC_RENDER_STAGE_STARS 5\n'
    if dh:
        defines += '#define DISTANT_HORIZONS\n'
    for i, name in enumerate(['UNKNOWN', 'LEAVES', 'STONE', 'WOOD', 'METAL', 'DIRT', 'GRASS', 'LAVA', 'DEEPSLATE', 'SNOW', 'SAND', 'TERRACOTTA', 'NETHER_STONE', 'WATER', 'AIR', 'ILLUMINATED']):
        defines += f'#define DH_BLOCK_{name} {i}\n'
    if path.name.startswith('dh_') and path.suffix == '.vsh':
        defines += 'int dhMaterialId;\n'
    # Iris resolves forward uniform references. Hoist declarations for standalone GL.
    uniforms = []
    src = re.sub(r'^\s*uniform\s+[^;]+;', lambda m: uniforms.append(m[0].strip()) or '', src, flags=re.M)
    src = src.replace(version, version + '\n' + defines + '\n'.join(dict.fromkeys(uniforms)), 1)
    src = re.sub(r'\btexture\b(?!\s*\()', 'gtexture', src)
    return src


def check(path, dh, options):
    shaders = []
    program = create_program()
    try:
        for stage, suffix in [(0x8B31, '.vsh'), (0x8B30, '.fsh')]:
            file = path.with_suffix(suffix)
            src = prepare(file, dh, options).encode()
            shader = create_shader(stage)
            shaders.append(shader)
            source_shader(shader, 1, C.byref(C.c_char_p(src)), None)
            compile_shader(shader)
            ok = integer()
            get_shader(shader, 0x8B81, C.byref(ok))
            if not ok.value:
                log = C.create_string_buffer(20000)
                log_shader(shader, len(log), None, log)
                Path('/tmp/yamashita-failed.glsl').write_bytes(src)
                raise RuntimeError(f'{file.relative_to(ROOT)} DH={dh}:\n{log.value.decode()}')
            attach(program, shader)
        link(program)
        ok = integer()
        get_program(program, 0x8B82, C.byref(ok))
        if not ok.value:
            log = C.create_string_buffer(20000)
            log_program(program, len(log), None, log)
            raise RuntimeError(f'{path.relative_to(ROOT)} DH={dh}: {log.value.decode()}')
    finally:
        delete_program(program)
        for shader in shaders:
            delete_shader(shader)


if __name__ == '__main__':
    paths = sorted(p for p in ROOT.rglob('*.vsh') if p.parent == ROOT or p.parent.name.startswith('world'))
    if len(sys.argv) > 1:
        paths = [p for p in paths if sys.argv[1] in str(p.relative_to(ROOT))]
    total = 0
    for dh in [False, True]:
        for path in paths:
            if path.name.startswith('dh_') and not dh:
                continue
            check(path, dh, {})
            total += 1
    # Exercise the actual low-cost path as well as all optional cloud programs.
    low = {'FLAT_LIGHTING': 1, 'ENABLE_HEAT_HAZE': 0, 'ENABLE_BLOOM': 0,
           'ENHANCED_CLOUDS': 0, 'CLOUD_SHADOWS': 0, 'ENABLE_PIXEL_DOF': 0,
           'ENABLE_MOTIONBLUR': 0, 'ENABLE_PUDDLES': 0, 'DH_SHADOWS': 1}
    for path in paths:
        check(path, True, low)
        total += 1
    print(f'PASS: {total} shader pairs compiled and linked (DH off/on, default/low effects).')
