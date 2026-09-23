# Yamashita Shimejize — Minecraft 26.2 + Distant Horizons

Experimental adaptation of [rindefault/Yamashita-Shimejize](https://github.com/rindefault/Yamashita-Shimejize), based on commit `e5f709fd149bf26f5c5d60ae8481b001fcac279a`.

**Status: alpha. GLSL compilation and depth tests have passed; visual validation inside Minecraft is still pending.** This is not an official release from the original author.

## Target environment

- Minecraft Java **26.2**, Fabric, and **OpenGL** rendering.
- Iris **1.11.4+mc26.2** and the Sodium version required by Iris (0.9.2).
- Distant Horizons **3.3.2-26.2-fabric-neoforge**.
- DH must use its OpenGL renderer, not Blaze3D. Compilation without DH is also checked.

This adapts the shaderpack; it does not modify the Minecraft, Iris, or DH JARs. It does not add Vulkan support.

## Installation

1. Run `python3 tools/build_pack.py` or use the generated ZIP in `dist/`.
2. Copy `Yamashita-Shimejize-mc26.2-DH-alpha.1.zip` into your instance's `shaderpacks` folder.
3. Select it in Iris. The ZIP contains `shaders/` directly at its root.
4. Start with the LOW or NORMAL profile, a normal render distance of 8–12 chunks, and DH set to 128 chunks. Adjust based on performance.

Enable shadows cast by LOD terrain using **Distant Horizons shadows** in the lighting options. They are disabled by default to limit rendering cost. Existing sunlight and nearby shadows remain available.

## Changes

- `dh_terrain`, `dh_water`, and `dh_shadow` programs for the Overworld, Nether, and End.
- Reuse of the original shader's lighting, fog, emissive materials, and water outputs; LODs use the color supplied by DH.
- Comparison of positions reconstructed with each projection, rather than depth values from different ranges.
- Shared depth handling for clouds, reflections, motion blur, depth of field, bloom, heat effects, and sky effect occlusion.
- Fog adjusted to DH's render distance for both nearby and distant terrain.
- Clipping of DH water/terrain behind normal geometry, with separate blending for water normals and identifiers.
- Explicit declarations for matrices missing from the original programs that use the shared transformation functions.

Iris 1.11.4 transforms depth reads and positions for reverse-Z rendering in 26.2. The pack keeps the depth convention Iris exposes to shaders; it does not invert the values a second time.

## Reproducible validation

On Linux with Python 3 and Mesa EGL/OpenGL installed:

```sh
python3 tools/check_shaders.py
python3 tools/test_scene_depth.py
python3 tools/build_pack.py
```

The GLSL check compiles and links 300 program pairs, covering dimension folders, DH enabled/disabled, and default/reduced effects. It expands includes, supplies Iris macros/attributes, and adapts some conventions for the standalone compiler. **It does not run Iris's Java transformer or replace testing in the game.**

The depth test executes the resolver's actual GLSL in a floating-point framebuffer with seven synthetic scenes: nearby surfaces, DH surfaces, overlaps, geometry near the far limit, and sky. It includes a case where comparing depth values directly would select the wrong surface.

## Pending in-game checks

- Load and reload the pack without errors, first with DH disabled and then enabled.
- Fly across the transition between normal chunks and LODs; check lighting, gaps, and fog during the day, at night, and in rain.
- Inspect oceans, coastlines, water from below the surface, and mountains in front of/behind clouds.
- Test reflections, DOF, camera movement, and optional DH shadows.
- Visit the Nether and End and switch dimensions; measure performance on the target GPU.

LODs use simplified colors and materials; DH's optional texture atlas is not integrated. Focusing on LODs does not have the temporal smoothing that Iris provides for normal terrain. Lighting/water continuity and the performance cost of effects still need to be evaluated in the game.

To diagnose failures, provide the Iris error or `logs/latest.log`, the pack settings, and a screenshot of the issue. Do not include tokens or account information.

## References and credits

- Original shader: [Yamashita Shimejize](https://modrinth.com/shader/yamashita-shimejize), by rindefault; derived from Miniature Shader. Its Modrinth listing declares the MIT license. This fork preserves the original files and their attribution.
- [Iris's Distant Horizons interface](https://shaders.properties/current/reference/mod-support/distant_horizons/).
- [Iris for 26.2](https://github.com/IrisShaders/Iris/tree/26.2), particularly `DepthTransformer`, `DHTerrainTransformer`, and `DHCompat`.
