#include "/shader.h"
#include "/common/getShadowDistortion.glsl"

varying vec3 dhShadowPos;
flat out int dhShadowMaterial;

void main() {
    dhShadowPos = gl_Vertex.xyz;
    dhShadowMaterial = dhMaterialId;
    gl_Position = gl_ProjectionMatrix * gl_ModelViewMatrix * gl_Vertex;
    gl_Position.xyz = getShadowDistortion(gl_Position.xyz);
}
