#ifndef YS_RENDER_DISTANCE_GLSL
#define YS_RENDER_DISTANCE_GLSL
#ifdef DISTANT_HORIZONS
uniform int dhRenderDistance;
#endif
float ysFogDistance(float vanillaFar) {
    #ifdef DISTANT_HORIZONS
        return max(vanillaFar, float(dhRenderDistance));
    #else
        return vanillaFar;
    #endif
}
#endif
