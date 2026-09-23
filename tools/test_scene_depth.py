#!/usr/bin/env python3
"""Render synthetic vanilla/DH depths through the actual GLSL surface resolver."""
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
