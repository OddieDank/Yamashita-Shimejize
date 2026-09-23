#ifndef YS_SCENE_DEPTH_GLSL
#define YS_SCENE_DEPTH_GLSL

// Iris 1.11.4 exposes forward-Z reads/projections to the pack even on 26.2.
// Do not invert these samples again. The two projections have different ranges.
#ifdef DISTANT_HORIZONS
uniform sampler2D dhDepthTex0;
uniform mat4 dhProjectionInverse;
#endif

struct YsSceneDepth {
    vec3 viewPos;
    bool hit;
    bool distant;
};

vec3 ysUnproject(mat4 inverseProjection, vec2 uv, float depth) {
    vec4 pos = inverseProjection * vec4(uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
    return pos.xyz / pos.w;
}

YsSceneDepth ysSceneDepth(vec2 uv) {
    YsSceneDepth scene;
    float depth = texture2D(depthtex0, uv).r;
    scene.hit = depth < 1.0;
    scene.distant = false;
    // A finite point on the sky ray avoids division by zero at an infinite far plane.
    scene.viewPos = ysUnproject(gbufferProjectionInverse, uv, scene.hit ? depth : 0.9999);
    #ifdef DISTANT_HORIZONS
        float dhDepth = texture2D(dhDepthTex0, uv).r;
        if (dhDepth < 1.0) {
            vec3 dhPos = ysUnproject(dhProjectionInverse, uv, dhDepth);
            if (!scene.hit || -dhPos.z < -scene.viewPos.z) {
                scene.viewPos = dhPos;
                scene.hit = true;
                scene.distant = true;
            }
        }
    #endif
    return scene;
}

// A common infinite-far depth metric for DOF and occlusion, not a depth-buffer
// value. Sky is exactly 1; all terrain (including beyond vanilla far) is < 1.
float ysDepthMetric(vec3 viewPos) {
    return min(1.0 - 0.05 / max(-viewPos.z, 0.05), 0.99999994);
}

float ysSceneDepthMetric(vec2 uv) {
    YsSceneDepth scene = ysSceneDepth(uv);
    return scene.hit ? ysDepthMetric(scene.viewPos) : 1.0;
}

float ysMetricDistance(float depth) {
    return 0.05 / max(1.0 - depth, 0.00000006);
}
#endif
