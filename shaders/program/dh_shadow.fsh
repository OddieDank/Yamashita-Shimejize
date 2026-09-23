#include "/shader.h"

varying vec3 dhShadowPos;
flat in int dhShadowMaterial;

void main() {
    if (dot(dhShadowPos, dhShadowPos) > SHADOW_MAX_DIST_SQUARED) discard;
    if (dhShadowMaterial == DH_BLOCK_WATER) discard;
    /* DRAWBUFFERS:0 */
    gl_FragData[0] = vec4(1.0);
}
