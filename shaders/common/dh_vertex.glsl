// Map DH's coarse material categories to the existing lighting classifications.
// Iris injects dhMaterialId; it must not be redeclared as an attribute.
uniform mat4 dhProjection;

vec4 mc_Entity;
void ysSetDhMaterial() {
    float id = 0.0;
    if (dhMaterialId == DH_BLOCK_WATER) id = 10008.0;
    if (dhMaterialId == DH_BLOCK_LAVA) id = 10068.0;
    if (dhMaterialId == DH_BLOCK_LEAVES) id = 10031.0;
    if (dhMaterialId == DH_BLOCK_ILLUMINATED) id = 10091.0;
    mc_Entity = vec4(id, 0.0, 0.0, 0.0);
}
