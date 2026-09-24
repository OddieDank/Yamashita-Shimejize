// DH supplies light levels, but its GL lightmap binding is not the external
// texture unit expected by Iris's "lightmap" sampler in the target versions.
// Build ambient light from those levels and the pack's existing sky colors;
// the normal terrain path continues to use Minecraft's lightmap texture.
vec4 ysDhAmbient(vec2 lightUV) {
    float sky = clamp((lightUV.y - 0.03125) * (16.0 / 15.0), 0.0, 1.0);
    float skyBrightness = sky / (4.0 - 3.0 * sky);
    #ifdef OVERWORLD
        vec3 skyAmbient = mix(ambientColor, vec3(1.0),
                              sunVisibility2 * (1.0 - 0.5 * rainFactor));
        return vec4(mix(vec3(0.04), skyAmbient, skyBrightness), 1.0);
    #else
        // Nether/End ambient is independent of the Overworld day/night cycle.
        return vec4(vec3(0.65), 1.0);
    #endif
}
