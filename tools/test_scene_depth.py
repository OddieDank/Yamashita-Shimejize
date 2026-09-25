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
''' + (ROOT / 'common/math.glsl').read_text() + (ROOT / 'common/dh_clip.glsl').read_text() + '''
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
    ('near roof outside API exclusion radius', None, 40, 16, 0, False),
    ('same roof after rotation', None, 40, 16, 55, False),
    ('LOD in front of normal geometry', 100, 80, 16, 0, True),
    ('LOD behind normal geometry', 80, 100, 16, 0, False),
    ('distant terrain against sky', None, 2048, 16, 0, True),
    ('near leaves with zero API exclusion', None, 24, 0, 0, False),
    ('past transition after rotation', None, 100, 16, 55, True),
]
for name in ['dh_terrain.vsh', 'dh_water.vsh']:
    program = make_program(prepare(ROOT / name, True, {}), fragment)
    bind(gl, 'glUseProgram', None, uint)(program)
    set_int(uniform(program, b'depthtex0'), 0)
    set_float(uniform(program, b'far'), 128)
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

# A whole dither tile must be empty near the camera, partially covered in the
# transition, and fully covered before the normal terrain ends. Test at two
# normal render distances without depending on a single pixel's Bayer threshold.
fragment = fragment.replace('varying vec3 worldPos;', 'uniform vec3 worldPos;')
program = make_program(vertex, fragment)
bind(gl, 'glUseProgram', None, uint)(program)
set_vec3 = bind(gl, 'glUniform3f', None, integer, C.c_float, C.c_float, C.c_float)
active_tex(0x84C2)
bind_tex(0x0DE1, textures[2])
tex_image(0x0DE1, 0, 0x8814, 4, 4, 0, 0x1908, 0x1406, None)
bind(gl, 'glViewport', None, integer, integer, integer, integer)(0, 0, 4, 4)
for key in [b'viewWidth', b'viewHeight']:
    set_float(uniform(program, key), 4)
set_int(uniform(program, b'depthtex0'), 0)
set_float(uniform(program, b'clipDistance'), 16)
projection(b'dhProjectionInverse', 16, 8192)
for normal_range in [64, 128]:
    set_float(uniform(program, b'far'), normal_range)
    counts = []
    for fraction in [.3, .4, .45, .5, .55, .6, 2.0]:
        distance = normal_range * fraction
        # Front-facing and side-facing points at the same chunk distance.
        for x, z in [(0, -distance), (distance, 0)]:
            set_vec3(uniform(program, b'worldPos'), x, 0, z)
            clear(0x4000)
            draw(0x0004, 0, 3)
            pixels = (C.c_float * 64)()
            read(0, 0, 4, 4, 0x1908, 0x1406, pixels)
            count = sum(pixels[i] > 0 for i in range(1, 64, 4))
            if x == 0:
                counts.append(count)
            else:
                assert count == counts[-1], ('camera direction changed coverage', counts, count)
    assert counts[:2] == [0, 0] and counts[-2:] == [16, 16], counts
    assert counts == sorted(counts) and 0 < counts[3] < 16, counts
print('PASS: 28 rendered transition tiles: no nearby LOD pixels, smooth coverage, intact far terrain.')

# Render the complete DH lighting path with a BLACK Minecraft lightmap. This
# models a missing/stale external binding, which standalone compilation cannot
# catch. Skylight, night, cave darkness and block lights must still work.
active_tex(0x84C2)
bind_tex(0x0DE1, textures[2])
tex_image(0x0DE1, 0, 0x8814, 1, 1, 0, 0x1908, 0x1406, None)
bind(gl, 'glViewport', None, integer, integer, integer, integer)(0, 0, 1, 1)
black_texture = uint()
gen_tex(1, C.byref(black_texture))
bind_tex(0x0DE1, black_texture)
tex_param(0x0DE1, 0x2801, 0x2600)
tex_param(0x0DE1, 0x2800, 0x2600)
tex_image(0x0DE1, 0, 0x8814, 1, 1, 0, 0x1908, 0x1406, (C.c_float * 4)(0,0,0,1))
identity = (C.c_float * 16)(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1)
matrix_mode(0x1700)
load_matrix(identity)
lightcoord = bind(gl, 'glMultiTexCoord2f', None, uint, C.c_float, C.c_float)
bind(gl, 'glColor4f', None, C.c_float, C.c_float, C.c_float, C.c_float)(.6,.6,.6,1)
bind(gl, 'glNormal3f', None, C.c_float, C.c_float, C.c_float)(1,0,0)
lighting_results = {}
for name, shadow_darkness in [(name, value) for name in ['dh_terrain', 'dh_water']
                              for value in [0.0, 0.4, 1.0]]:
    # Isolate surface lighting: sky-colored fog would hide a black-lightmap bug.
    sources = [prepare(ROOT / (name + suffix), True, {'SHADOW_DARKNESS': shadow_darkness}).replace(
        '#define ENABLE_FOG', '// Fog disabled for the lighting regression')
        for suffix in ['.vsh', '.fsh']]
    material = 'DH_BLOCK_WATER' if name == 'dh_water' else 'DH_BLOCK_GRASS'
    sources[0] = sources[0].replace('int dhMaterialId;', f'int dhMaterialId = {material};')
    program = make_program(*sources)
    bind(gl, 'glUseProgram', None, uint)(program)
    for key in [b'gbufferModelView', b'gbufferModelViewInverse']:
        set_matrix(uniform(program, key), 1, 0, identity)
    set_matrix(uniform(program, b'dhProjection'), 1, 0, forward(16, 8192))
    set_matrix(uniform(program, b'gbufferProjection'), 1, 0, forward(.05, 128))
    projection(b'dhProjectionInverse', 16, 8192)
    projection(b'gbufferProjectionInverse', .05, 128)
    set_int(uniform(program, b'depthtex0'), 0)
    set_int(uniform(program, b'lightmap'), 2)
    set_int(uniform(program, b'dhRenderDistance'), 2016)
    for key, value in [(b'viewWidth', 1), (b'viewHeight', 1), (b'far', 128),
                       (b'clipDistance', 16), (b'screenBrightness', .5)]:
        set_float(uniform(program, key), value)
    set_vec3(uniform(program, b'skyColor'), .5,.7,1)
    set_vec3(uniform(program, b'fogColor'), .6,.7,.8)
    set_vec3(uniform(program, b'shadowLightPosition'), 0,1000,0)
    luminances = []
    for time, block, sky in [(6000,0,15), (18000,0,15), (6000,0,0), (6000,15,0)]:
        set_int(uniform(program, b'worldTime'), time)
        set_float(uniform(program, b'timeAngle'), time / 24000)
        lightcoord(0x84C2, (block+.5)/16, (sky+.5)/16)
        clear(0x4000)
        begin(0x0004)
        for x, y in [(-256,-256), (768,-256), (-256,768)]:
            vertex3(x, y, -256)
        end()
        pixel = (C.c_float * 4)()
        read(0, 0, 1, 1, 0x1908, 0x1406, pixel)
        assert all(math.isfinite(x) for x in pixel), (name, time, block, sky, tuple(pixel))
        luminances.append(sum(a*b for a,b in zip(pixel, [.299,.587,.114])))
    day, night, cave, torch = luminances
    lighting_results[name, shadow_darkness] = luminances
    if shadow_darkness == 0.4:
        assert day > .08, (name, 'unlit daylight LOD', luminances)
        assert night < day * .6 and cave < day * .6, (name, luminances)
    assert torch > cave + .05, (name, 'missing block light', luminances)
    print(f'PASS: {name} lighting, shadow darkness {shadow_darkness}: day/night/cave/torch = '
          + '/'.join(f'{v:.3f}' for v in luminances))
for name in ['dh_terrain', 'dh_water']:
    assert lighting_results[name, 0.0][1] > lighting_results[name, 0.4][1] > lighting_results[name, 1.0][1], name

# Reflections must validate the texel *after* wave displacement. Model a red
# target surrounded by blue foreground/background/water/sky texels: only a
# neighbor on the same reflected surface may contribute blue to the result.
reflection_header = '''#version 330 compatibility
#define DISTANT_HORIZONS
uniform sampler2D depthtex0, colortex0, colortex7;
uniform mat4 gbufferProjection, gbufferProjectionInverse;
uniform mat4 gbufferModelView, gbufferModelViewInverse;
uniform vec3 testRay, testOrigin;
'''
reflection_source = ''.join((ROOT / p).read_text() for p in [
    'common/math.glsl', 'common/transformations.fsh', 'common/scene_depth.glsl',
    'common/getReflectionColor.fsh'])
program = make_program(vertex, reflection_header + reflection_source + '''
void main() {
    gl_FragColor = getValidatedReflectionColor(vec2(0.53), testRay, testOrigin,
                                              vec3(0.0, 1.0, 0.0), 0.0);
}
''')
bind(gl, 'glUseProgram', None, uint)(program)
refl_textures = (uint * 4)()
gen_tex(4, refl_textures)
for i, key in enumerate([b'depthtex0', b'dhDepthTex0', b'colortex0', b'colortex7']):
    active_tex(0x84C0 + i)
    bind_tex(0x0DE1, refl_textures[i])
    # Linear filtering deliberately stresses silhouette boundaries. Sampling
    # texel centers must keep the hit's depth, material and color consistent.
    tex_param(0x0DE1, 0x2801, 0x2601)
    tex_param(0x0DE1, 0x2800, 0x2601)
    set_int(uniform(program, key), i)
vanilla_depth = projection(b'gbufferProjectionInverse', .05, 128)
dh_depth = projection(b'dhProjectionInverse', 4, 8192)
for key in [b'viewWidth', b'viewHeight']:
    set_float(uniform(program, key), 16)
set_vec3(uniform(program, b'testRay'), .625, .625, -10)
set_vec3(uniform(program, b'testOrigin'), 0, -1, -2)
colors = [0.,0.,1.,1.] * 256
center = 8 * 16 + 8
colors[center*4:center*4+4] = [1.,0.,0.,1.]


def upload_reflection(i, values, components=1):
    active_tex(0x84C0 + i)
    bind_tex(0x0DE1, refl_textures[i])
    tex_image(0x0DE1, 0, 0x8814 if components == 4 else 0x822E, 16, 16, 0,
              0x1908 if components == 4 else 0x1903, 0x1406,
              (C.c_float * len(values))(*values))


upload_reflection(2, colors, 4)
for distant in [False, True]:
    for neighbor, water, expected in [(6,False,(1,0,0)), (30,False,(1,0,0)),
            (None,False,(1,0,0)), (10,True,(1,0,0)), (10,False,(0,0,1))]:
        distances = [neighbor] * 256
        distances[center] = 10
        upload_reflection(0, [1. if distant else vanilla_depth(d) for d in distances])
        upload_reflection(1, [dh_depth(d) if distant else 1. for d in distances])
        masks = [float(water),float(water),0.,1.] * 256
        masks[center*4:center*4+4] = [0.,0.,0.,1.]
        upload_reflection(3, masks, 4)
        draw(0x0004, 0, 3)
        pixel = (C.c_float * 4)()
        read(0, 0, 1, 1, 0x1908, 0x1406, pixel)
        assert pixel[3] > 0 and all(abs(pixel[i]-expected[i]) < .001 for i in range(3)), (
            'reflection sampled a different surface', distant, neighbor, water, tuple(pixel))
    for invalid in ['sky', 'water', 'off ray', 'below plane']:
        distance = None if invalid == 'sky' else 10
        upload_reflection(0, [1. if distant else vanilla_depth(distance)] * 256)
        upload_reflection(1, [dh_depth(distance) if distant else 1.] * 256)
        upload_reflection(3, [float(invalid == 'water'),0.,0.,1.] * 256, 4)
        set_vec3(uniform(program, b'testRay'), .625,.625,-20 if invalid == 'off ray' else -10)
        set_vec3(uniform(program, b'testOrigin'), 0,2 if invalid == 'below plane' else -1,-2)
        draw(0x0004, 0, 3)
        pixel = (C.c_float * 4)()
        read(0, 0, 1, 1, 0x1908, 0x1406, pixel)
        assert pixel[3] == 0, (invalid, tuple(pixel))
    set_vec3(uniform(program, b'testRay'), .625,.625,-10)
    set_vec3(uniform(program, b'testOrigin'), 0,-1,-2)
print('PASS: reflection texels reject foreground/background leaks, water, sky and false ray hits.')

# Exercise both complete ray marchers as well: the fix must retain a valid
# reflection, rather than merely make every reflection transparent.
for puddle in [False, True]:
    if puddle:
        source = prepare(ROOT / 'final.fsh', True, {}).replace('void main()', 'void unusedFinalMain()')
        source += '''
void main() {
    gl_FragData[0] = getPuddleReflectionColor(vec2(0.5), 0.975,
                         vec3(0.0, 1.0, 0.0), vec3(0.0, -1.0, -2.0));
}
'''
    else:
        source = reflection_header + reflection_source + '''
void main() {
    gl_FragColor = getReflectionColor(0.975, vec3(0.0, 1.0, 0.0),
                                     vec3(0.0, -1.0, -2.0), 0.0);
}
'''
    program = make_program(vertex, source)
    bind(gl, 'glUseProgram', None, uint)(program)
    for i, key in enumerate([b'depthtex0', b'dhDepthTex0', b'colortex0', b'colortex7']):
        set_int(uniform(program, key), i)
    for key in [b'viewWidth', b'viewHeight']:
        set_float(uniform(program, key), 16)
    set_matrix(uniform(program, b'gbufferProjection'), 1, 0, forward(.05, 128))
    set_matrix(uniform(program, b'gbufferModelViewInverse'), 1, 0, identity)
    vanilla_depth = projection(b'gbufferProjectionInverse', .05, 128)
    dh_depth = projection(b'dhProjectionInverse', 4, 8192)
    upload_reflection(2, [0.,1.,0.,1.] * 256, 4)
    upload_reflection(3, [0.] * 1024, 4)
    for distant in [False, True]:
        for distance in [10, None]:
            upload_reflection(0, [1. if distant else vanilla_depth(distance)] * 256)
            upload_reflection(1, [dh_depth(distance) if distant else 1.] * 256)
            draw(0x0004, 0, 3)
            pixel = (C.c_float * 4)()
            read(0, 0, 1, 1, 0x1908, 0x1406, pixel)
            assert (pixel[3] > 0) == (distance is not None), (puddle, distant, distance, tuple(pixel))
            if distance is not None:
                assert abs(pixel[1] - 1.) < .001, tuple(pixel)
print('PASS: water and puddle ray marchers retain valid normal/DH reflections and reject sky.')

# Exercise the actual composite pass: menu controls must affect the image
# before posterization, and dithering must preserve average dark-tone energy.
active_tex(0x84C2)
bind_tex(0x0DE1, textures[2])
tex_image(0x0DE1, 0, 0x8814, 8, 8, 0, 0x1908, 0x1406, None)
bind(gl, 'glViewport', None, integer, integer, integer, integer)(0, 0, 8, 8)
tone_vertex = vertex.replace('void main()', 'varying vec2 texcoord;\nvoid main()').replace(
    'gl_Position =', 'texcoord = p;\n    gl_Position =')
tones = [0., .003, .01, .04, .25, .5, .75, 1.]
for dh in [False, True]:
    results = {}
    for brightness, contrast in [(-1.,1.), (0.,1.), (.5,1.), (1.,1.), (0.,0.), (0.,2.)]:
        options = {'ENHANCED_CLOUDS': 0, 'BRIGHTNESS': brightness, 'CONTRAST': contrast}
        program = make_program(tone_vertex, prepare(ROOT / 'composite.fsh', dh, options))
        bind(gl, 'glUseProgram', None, uint)(program)
        set_int(uniform(program, b'colortex0'), 2)
        set_int(uniform(program, b'depthtex0'), 0)
        set_int(uniform(program, b'dhDepthTex0'), 1)
        for key in [b'viewWidth', b'viewHeight']:
            set_float(uniform(program, key), 8.)
        set_matrix(uniform(program, b'gbufferModelViewInverse'), 1, 0, identity)
        projection(b'gbufferProjectionInverse', .05, 128)
        projection(b'dhProjectionInverse', 4, 8192)
        upload_reflection(0, [1.] * 256)
        upload_reflection(1, [1.] * 256)
        means = []
        for tone in tones:
            upload_reflection(2, [tone,tone,tone,1.] * 256, 4)
            draw(0x0004, 0, 3)
            pixels = (C.c_float * (8*8*4))()
            read(0, 0, 8, 8, 0x1908, 0x1406, pixels)
            assert all(math.isfinite(v) and 0. <= v <= 1. for v in pixels)
            means.append(sum(pixels[::4]) / 64)
        results[brightness, contrast] = means
        assert all(a <= b for a,b in zip(means, means[1:])), means
    original = results[0.,1.]
    assert max(abs(a-b) for a,b in zip(original, tones)) < 1./(24*16), original
    assert results[1.,1.][1] > .04, 'Brightness did not recover dark detail'
    for i in range(1,7):
        assert results[-1.,1.][i] <= original[i] < results[.5,1.][i] < results[1.,1.][i]
    assert all(abs(v-.5) < .001 for v in results[0.,0.]), 'Contrast is not connected'
    assert results[0.,2.][4] == 0. and results[0.,2.][6] == 1.
    for brightness in [-1.,0.,.5,1.]:
        assert results[brightness,1.][0] == 0. and results[brightness,1.][7] == 1.
print('PASS: 96 composite renders verify brightness, contrast and dark-tone dithering with DH off/on.')
