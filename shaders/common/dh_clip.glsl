uniform sampler2D depthtex0;
uniform mat4 dhProjectionInverse;
uniform float clipDistance;

void ysClipDhBehindVanilla() {
    // Restore DH's radial overdraw prevention, including pixels where vanilla
    // depth is sky (leaf gaps and the edges of roofs cannot depth-occlude LODs).
    // worldPos is camera-relative and does not change with the viewing direction.
    if (length(worldPos) < clipDistance) discard;

    vec2 uv = gl_FragCoord.xy / vec2(viewWidth, viewHeight);
    float depth = texture2D(depthtex0, uv).r;
    if (depth < 1.0) {
        vec4 vanilla = gbufferProjectionInverse * vec4(uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
        vec4 distant = dhProjectionInverse * vec4(uv * 2.0 - 1.0, gl_FragCoord.z * 2.0 - 1.0, 1.0);
        if (-vanilla.z / vanilla.w <= -distant.z / distant.w) discard;
    }
}
