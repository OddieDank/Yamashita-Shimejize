# Yamashita Shimejize — Minecraft 26.2 + Distant Horizons

Experimental adaptation of [rindefault/Yamashita-Shimejize](https://github.com/rindefault/Yamashita-Shimejize), based on commit `e5f709fd149bf26f5c5d60ae8481b001fcac279a`.

**Status: alpha.4. The user confirmed that alpha.3 fixed dark LODs and nearby silhouettes. Alpha.4 targets remaining reflection artifacts and cloud movement with view bobbing. GLSL and synthetic rendering checks have passed; visual confirmation of alpha.4 is still pending.** This is not an official release from the original author.

## Target environment

- Minecraft Java **26.2**, Fabric, and **OpenGL** rendering.
- Iris **1.11.4+mc26.2** and the Sodium version required by Iris (0.9.2).
- Distant Horizons **3.3.2-26.2-fabric-neoforge**.
- DH must use its OpenGL renderer, not Blaze3D. Compilation without DH is also checked.

This adapts the shaderpack; it does not modify the Minecraft, Iris, or DH JARs. It does not add Vulkan support.

## Installation

1. Run `python3 tools/build_pack.py` or use the generated ZIP in `dist/`.
2. Copy `Yamashita-Shimejize-mc26.2-DH-alpha.4.zip` into your instance's `shaderpacks` folder.
3. Select it in Iris. The ZIP contains `shaders/` directly at its root.
4. Start with the LOW or NORMAL profile, a normal render distance of 8–12 chunks, and DH set to 128 chunks. Adjust based on performance.

Enable shadows cast by LOD terrain using **Distant Horizons shadows** in the lighting options. They are disabled by default to limit rendering cost. Existing sunlight and nearby shadows remain available.

## Changes

- `dh_terrain`, `dh_water`, and `dh_shadow` programs for the Overworld, Nether, and End.
- Reuse of the original shader's lighting, fog, emissive materials, and water outputs; LODs use DH's color and light levels with ambient lighting independent of Minecraft's lightmap texture binding.
- Comparison of positions reconstructed with each projection, rather than depth values from different ranges.
- Shared depth handling for clouds, reflections, motion blur, depth of field, bloom, heat effects, and sky effect occlusion.
- Fog adjusted to DH's render distance for both nearby and distant terrain.
- Clipping of DH water/terrain behind normal geometry, with separate blending for water normals and identifiers.
- Explicit declarations for matrices missing from the original programs that use the shared transformation functions.

Iris 1.11.4 transforms depth reads and positions for reverse-Z rendering in 26.2. The pack keeps the depth convention Iris exposes to shaders; it does not invert the values a second time.

### Alpha.4: reflections and normal clouds

- Water and puddle reflections now refine only after the ray crosses scene depth, and require a bounded final depth match above the reflecting plane. The previous proximity heuristic could accept object silhouettes without a real intersection. Rays stop before passing behind the camera; the 16-step budget is unchanged.
- The exact color texel is rechecked after wave displacement and pixelation. If the offset lands on foreground geometry, another depth layer, water or sky, sampling falls back to the validated hit. Depth, material and color samples use matching texel centers. Water normals are normalized and Fresnel is clamped.
- With **Enhanced Clouds disabled**, the pack explicitly selects Minecraft's fancy clouds and disables DH's separate cloud renderer through Iris's `dhClouds=off` property. The target Iris/DH generic cloud path uses a different model-view matrix from terrain and is susceptible to view-bobbing drift. This bypasses that path without disabling view bobbing or DH terrain. Enhanced clouds continue to use the pack's own rendering.

These remain screen-space reflections: off-screen and hidden geometry cannot be recovered, and rejected intersections can fade out. Check moving silhouettes, water/puddle edges and performance in the game.

### Alpha.3: dark LODs and persistent silhouettes

- **Near transition:** DH's API clip distance only removes the closest geometry. It still allowed coarse shapes beside nearby leaves and roofs. Terrain and water now fade in between 40% and 60% of the normal render distance, using cylindrical distance and the pack's Bayer dithering. At 8 normal chunks, that is approximately 51–77 blocks. The transition discards both color and depth; distant geometry remains fully visible. As with any distance-based transition, missing normal chunks can expose gaps while loading or flying quickly.
- **Ambient light:** the installed DH 3.3.2 OpenGL renderer binds its lightmap on texture unit 0, while Iris 1.11.4's external `lightmap` sampler expects unit 2. Relying on that external binding in DH passes can produce black ambient light. LOD terrain and water now derive ambient light from their skylight levels and the pack's existing day/night/weather colors. Block lights, sunlight and shadows still use the existing lighting path. Normal terrain retains its original lightmap sampling. The LOD ambient approximation still needs visual comparison at the transition, including night and rain.

The user-provided tutorial explains compatibility attributes, LOD vertex color, light levels, depth rejection and fog for Minecraft 1.20.6. The target-version JARs were also inspected: their texture binding and clipping behavior cannot be inferred from that older tutorial alone.

### Alpha.2: nearby LOD overlap

Terrain and water now explicitly use `dhProjection` when writing depth, matching `dhProjectionInverse` in the clipping and post-processing passes. With DH 3.3.2, the legacy projection used by `ftransform()` can have a different near plane: DH caps its raster projection near plane at 7.5 blocks in the usual case, while Iris builds `dhProjection` from DH's API clip distance. Mixing these matrices reconstructed incorrect distances.

Both passes also apply DH's supplied `clipDistance` as a camera-relative radial exclusion. The old depth-only comparison could not remove simplified LODs protruding into sky pixels beside leaves and roofs. In-game testing showed this exclusion was insufficient; alpha.3 adds the wider transition described above.

## Reproducible validation

On Linux with Python 3 and Mesa EGL/OpenGL installed:

```sh
python3 tools/check_shaders.py
python3 tools/test_scene_depth.py
python3 tools/build_pack.py
```

The GLSL check compiles and links 300 program pairs, covering dimension folders, DH enabled/disabled, and default/reduced effects. It expands includes, supplies Iris macros/attributes, and adapts some conventions for the standalone compiler. **It does not run Iris's Java transformer or replace testing in the game.**

The depth test executes the resolver's actual GLSL in a floating-point framebuffer with seven synthetic scenes: nearby surfaces, DH surfaces, overlaps, geometry near the far limit, and sky. It includes a case where comparing depth values directly would select the wrong surface.

It also renders 18 cases through the real DH terrain/water vertex programs and shared clipping GLSL, checking near exclusion against sky, camera rotation, depth ordering, distant terrain, and a deliberately mismatched legacy projection. A further 28 dither tiles check transition coverage at two normal render distances and two orientations. Eight full terrain/water lighting cases deliberately bind a black Minecraft lightmap and check daylight, night, cave darkness and block light with fog disabled. Replaying the old lightmap-dependent path fails the daylight check.

Reflection tests add 18 cases for wave offsets, foreground/background boundaries, water, sky, ray mismatch and the reflecting plane, plus eight cases through the complete water/puddle ray marchers. They retain valid reflections with normal and DH depths. There are 87 rendered scenarios in total. Cloud renderer selection was checked against the installed Iris 1.11.4 property parser; view-bobbing behavior still requires an in-game check.

## Pending in-game checks

- With alpha.4 selected, revisit the tree and lamp beside water, move and turn the camera, and check reflection edges. Test rain puddles as well.
- Disable Enhanced Clouds and walk/sprint with view bobbing enabled. Confirm that Minecraft's normal clouds remain aligned with the world; also test Enhanced Clouds enabled.
- Keep DH enabled and check silhouettes and leaf gaps, then move toward distant terrain to inspect the transition and compare nearby/distant brightness.
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
