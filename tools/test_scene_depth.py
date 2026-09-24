#!/usr/bin/env python3
"""Render GLSL depth resolution, DH vertex projection and overlap clipping."""
import ctypes as C
import math
from check_shaders import (ROOT, gl, bind, ptr, uint, integer, create_shader,
    source_shader, compile_shader, get_shader, log_shader, create_program,
    attach, link, get_program, log_program)

vertex = '''#version 330 compatibility
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
'''
fragment = '''#version 330 compatibility
#define DISTANT_HORIZONS
uniform sampler2D depthtex0;
uniform mat4 gbufferProjectionInverse;
''' + (ROOT / 'common/scene_depth.glsl').read_text() + '''
out vec4 result;
void main() {
    YsSceneDepth scene = ysSceneDepth(vec2(0.5));
    result = vec4(-scene.viewPos.z, float(scene.hit), float(scene.distant),
                  scene.hit ? ysDepthMetric(scene.viewPos) : 1.0);
}
'''
def make_program(vertex, fragment):
    program = create_program()
    for kind, text in [(0x8B31, vertex), (0x8B30, fragment)]:
        shader = create_shader(kind)
        source_shader(shader, 1, C.byref(C.c_char_p(text.encode())), None)
        compile_shader(shader)
        ok = integer()
        get_shader(shader, 0x8B81, C.byref(ok))
        log = C.create_string_buffer(10000)
        log_shader(shader, len(log), None, log)
        assert ok.value, log.value.decode()
        attach(program, shader)
    link(program)
    ok = integer()
    get_program(program, 0x8B82, C.byref(ok))
    log_program(program, len(log), None, log)
    assert ok.value, log.value.decode()
    return program


program = make_program(vertex, fragment)
bind(gl, 'glUseProgram', None, uint)(program)
uniform = bind(gl, 'glGetUniformLocation', integer, uint, C.c_char_p)
set_int = bind(gl, 'glUniform1i', None, integer, integer)
set_matrix = bind(gl, 'glUniformMatrix4fv', None, integer, integer, uint, ptr)
gen_tex = bind(gl, 'glGenTextures', None, integer, ptr)
bind_tex = bind(gl, 'glBindTexture', None, uint, uint)
tex_image = bind(gl, 'glTexImage2D', None, uint, integer, integer, integer, integer, integer, uint, uint, ptr)
tex_param = bind(gl, 'glTexParameteri', None, uint, uint, integer)
active_tex = bind(gl, 'glActiveTexture', None, uint)
textures = (uint * 3)()
gen_tex(3, textures)
for i, name in enumerate([b'depthtex0', b'dhDepthTex0']):
    active_tex(0x84C0 + i)
    bind_tex(0x0DE1, textures[i])
    tex_param(0x0DE1, 0x2801, 0x2600)
    tex_param(0x0DE1, 0x2800, 0x2600)
    set_int(uniform(program, name), i)


def projection(name, near, far):
    a = -(far + near) / (far - near)
    b = -2 * far * near / (far - near)
    # Inverse of a unit-aspect perspective matrix, column-major.
    inverse = (C.c_float * 16)(1,0,0,0, 0,1,0,0, 0,0,0,1/b, 0,0,-1,a/b)
    set_matrix(uniform(program, name), 1, 0, inverse)
    return lambda distance: 1.0 if distance is None else (far - near * far / distance) / (far - near)


vanilla_depth = projection(b'gbufferProjectionInverse', 0.05, 128.0)
dh_depth = projection(b'dhProjectionInverse', 4.0, 8192.0)
active_tex(0x84C2)
bind_tex(0x0DE1, textures[2])
tex_image(0x0DE1, 0, 0x8814, 1, 1, 0, 0x1908, 0x1406, None)
fbo = uint()
bind(gl, 'glGenFramebuffers', None, integer, ptr)(1, C.byref(fbo))
bind(gl, 'glBindFramebuffer', None, uint, uint)(0x8D40, fbo)
bind(gl, 'glFramebufferTexture2D', None, uint, uint, uint, uint, integer)(0x8D40, 0x8CE0, 0x0DE1, textures[2], 0)
assert bind(gl, 'glCheckFramebufferStatus', uint, uint)(0x8D40) == 0x8CD5
bind(gl, 'glViewport', None, integer, integer, integer, integer)(0, 0, 1, 1)
draw = bind(gl, 'glDrawArrays', None, uint, integer, integer)
read = bind(gl, 'glReadPixels', None, integer, integer, integer, integer, uint, uint, ptr)

# Near/far ordering deliberately differs from raw depth ordering in case 3.
cases = [(12, 256, 12, False), (None, 2048, 2048, True),
         (100, 80, 80, True), (80, 100, 80, False),
         (None, 8190, 8190, True), (None, None, None, False),
         (24, None, 24, False)]
for vanilla, distant, expected, expect_dh in cases:
    for i, value in enumerate([vanilla_depth(vanilla), dh_depth(distant)]):
        active_tex(0x84C0 + i)
        bind_tex(0x0DE1, textures[i])
        tex_image(0x0DE1, 0, 0x822E, 1, 1, 0, 0x1903, 0x1406, C.byref(C.c_float(value)))
    draw(0x0004, 0, 3)
    pixel = (C.c_float * 4)()
    read(0, 0, 1, 1, 0x1908, 0x1406, pixel)
    distance, hit, from_dh, metric = pixel
    assert all(math.isfinite(x) for x in pixel), tuple(pixel)
    assert bool(hit) == (expected is not None), (vanilla, distant, tuple(pixel))
    assert bool(from_dh) == expect_dh, (vanilla, distant, tuple(pixel))
    if expected is not None:
        assert math.isclose(distance, expected, rel_tol=0.001), (expected, distance)
        assert metric < 1.0, 'Distant geometry was classified as sky'
    else:
        assert metric == 1.0
print(f'PASS: {len(cases)} rendered depth cases, including overlap, far terrain and sky.')

# Exercise the real DH terrain/water vertex paths and shared fragment clipping.
# Iris's legacy matrix can have a 7.5-block near plane while dhProjection uses
# the API distance (16 here). Both drawing and reconstruction must use the latter.
from check_shaders import prepare

fragment = '''#version 330 compatibility
uniform float viewWidth, viewHeight;
uniform mat4 gbufferProjectionInverse;
varying vec3 worldPos;
''' + (ROOT / 'common/dh_clip.glsl').read_text() + '''
out vec4 result;
void main() {
    ysClipDhBehindVanilla();
    vec4 p = dhProjectionInverse * vec4(0.0, 0.0, gl_FragCoord.z * 2.0 - 1.0, 1.0);
    result = vec4(-p.z / p.w, 1.0, 1.0, 1.0);
}
'''
set_float = bind(gl, 'glUniform1f', None, integer, C.c_float)
matrix_mode = bind(gl, 'glMatrixMode', None, uint)
load_matrix = bind(gl, 'glLoadMatrixf', None, ptr)
begin = bind(gl, 'glBegin', None, uint)
end = bind(gl, 'glEnd', None)
vertex3 = bind(gl, 'glVertex3f', None, C.c_float, C.c_float, C.c_float)
clear = bind(gl, 'glClear', None, uint)


def forward(near, far):
    return (C.c_float * 16)(1,0,0,0, 0,1,0,0,
        0,0,-(far+near)/(far-near),-1, 0,0,-2*far*near/(far-near),0)


# name, normal surface distance, LOD distance, radial exclusion, yaw, visibility
overlap_cases = [
    ('sky beside nearby leaves', None, 24, 32, 0, False),
    ('same leaves after camera rotation', None, 24, 32, 55, False),
    ('outside exclusion radius', None, 40, 32, 0, True),
    ('outside radius after rotation', None, 40, 32, 55, True),
    ('LOD in front of normal geometry', 100, 80, 16, 0, True),
    ('LOD behind normal geometry', 80, 100, 16, 0, False),
    ('distant terrain against sky', None, 2048, 16, 0, True),
    ('zero exclusion', None, 24, 0, 0, True),
]
for name in ['dh_terrain.vsh', 'dh_water.vsh']:
    program = make_program(prepare(ROOT / name, True, {}), fragment)
    bind(gl, 'glUseProgram', None, uint)(program)
    set_int(uniform(program, b'depthtex0'), 0)
    for key in [b'viewWidth', b'viewHeight']:
        set_float(uniform(program, key), 1)
    vanilla_depth = projection(b'gbufferProjectionInverse', .05, 128)
    projection(b'dhProjectionInverse', 16, 8192)
    set_matrix(uniform(program, b'dhProjection'), 1, 0, forward(16, 8192))
    matrix_mode(0x1701)  # GL_PROJECTION: deliberately differs from dhProjection.
    load_matrix(forward(7.5, 8192))
    for label, vanilla, distance, radius, yaw, visible in overlap_cases:
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        rotation = (C.c_float * 16)(c,0,-s,0, 0,1,0,0, s,0,c,0, 0,0,0,1)
        inverse = (C.c_float * 16)(c,0,s,0, 0,1,0,0, -s,0,c,0, 0,0,0,1)
        matrix_mode(0x1700)  # GL_MODELVIEW
        load_matrix(rotation)
        set_matrix(uniform(program, b'gbufferModelViewInverse'), 1, 0, inverse)
        set_float(uniform(program, b'clipDistance'), radius)
        active_tex(0x84C0)
        bind_tex(0x0DE1, textures[0])
        tex_image(0x0DE1, 0, 0x822E, 1, 1, 0, 0x1903, 0x1406,
                  C.byref(C.c_float(vanilla_depth(vanilla))))
        clear(0x4000)  # A discarded fragment must leave the clear color intact.
        begin(0x0004)
        for x, y in [(-distance, -distance), (3*distance, -distance), (-distance, 3*distance)]:
            vertex3(c*x + s*distance, y, s*x - c*distance)
        end()
        pixel = (C.c_float * 4)()
        read(0, 0, 1, 1, 0x1908, 0x1406, pixel)
        assert bool(pixel[1]) == visible, (name, label, tuple(pixel))
        if visible:
            assert math.isclose(pixel[0], distance, rel_tol=.001), (name, label, tuple(pixel))
print(f'PASS: {2 * len(overlap_cases)} rendered DH clipping/projection cases (terrain and water).')
