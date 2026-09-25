# Yamashita Shimejize — Minecraft 26.2 + Distant Horizons

## Shader ready to use

[Yamashita-Shimejize-DH](Yamashita-Shimejize-mc26.2-DH-alpha.5.zip)

Experimental adaptation of [rindefault/Yamashita-Shimejize](https://github.com/rindefault/Yamashita-Shimejize), based on commit `e5f709fd149bf26f5c5d60ae8481b001fcac279a`.

I wanted to play minecraft with stylized shaders and distant horizons, i thought this shader was very beautiful but it wasn't compatible, so here's an attempt to adapt it. I found it to be playable at this point.

Also i play with a latitude 5420, so its potato friendly 

**Status: alpha.5. Alpha.4 works well after extensive in-game testing. Alpha.5 connects brightness, contrast and surface shadow darkness controls and preserves dark tones during posterization. Automated checks pass; alpha.5 still needs in-game visual confirmation.** This is not an official release from the original author.

## Target environment

- Minecraft Java **26.2**, Fabric, and **OpenGL** rendering.
- Iris **1.11.4+mc26.2** and the Sodium version required by Iris (0.9.2).
- Distant Horizons **3.3.2-26.2-fabric-neoforge**.
- DH must use its OpenGL renderer, not Blaze3D. Compilation without DH is also checked.

This adapts the shaderpack; it does not modify the Minecraft, Iris, or DH JARs. It does not add Vulkan support.

## Installation

1. Run `python3 tools/build_pack.py` or use the generated ZIP in `dist/`.
2. Copy `Yamashita-Shimejize-mc26.2-DH-alpha.5.zip` into your instance's `shaderpacks` folder.
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

### Alpha.5: night visibility and working image controls

- **Brightness** and **Contrast** were declared in the menu but never used by a rendering pass. They now adjust the image before posterization: positive brightness lifts dark tones with a gamma curve, while contrast adjusts around middle gray. Defaults remain 0.0 and 1.0. These controls affect the whole image, including daytime, water and the sky.
- The Bayer threshold was incorrectly divided by the number of posterization levels before rounding, systematically crushing dark detail. It now spans the full threshold range, preserving average tone brightness through dithering.
- **Shadow Darkness** previously affected only enhanced cloud shadows. Surface programs used a fixed 0.6 attenuation. Terrain, entities, blocks, water and their DH paths now use the setting, retaining the original attenuation at its default of 0.4. This changes ambient shadow attenuation, not shadow-map coverage or all directional lighting.

For better night visibility, start with **Lighting → Brightness = 0.5**, **Contrast = 1.0**, and raise Brightness toward **1.0** as needed. Lower Shadow Darkness toward **0.0–0.2** if desired. Sun Brightness mainly controls direct sunlight; the terrain's direct contribution is gated off at night. The Minecraft brightness slider already influences the lighting model, but could not recover detail discarded by posterization. Previously saved Contrast values above 1.0 now take effect and can hide dark detail again. Brightness preserves true black; it cannot recover texture information already lost upstream.

With **Enhanced Clouds off**, height comes from Minecraft's normal cloud renderer. The installed 26.2 Overworld dimension defines a cloud base at **Y=192.33**, and the pack's cloud vertex shader does not lower it. To move that layer higher with Sodium Extra, enable **Cloud Height Override** and set **Cloud Height** to **256** or **320** in its video options. The override is currently disabled in the tested instance. This also affects normal clouds outside this pack; enhanced clouds retain their separate layers. No game configuration files are changed by installing this ZIP.

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

It also renders 18 cases through the real DH terrain/water vertex programs and shared clipping GLSL, checking near exclusion against sky, camera rotation, depth ordering, distant terrain, and a deliberately mismatched legacy projection. A further 28 dither tiles check transition coverage at two normal render distances and two orientations. Twenty-four full terrain/water lighting cases deliberately bind a black Minecraft lightmap and check daylight, night, cave darkness and block light with fog disabled at three Shadow Darkness settings. Replaying the old lightmap-dependent path fails the default daylight check.

Reflection tests add 18 cases for wave offsets, foreground/background boundaries, water, sky, ray mismatch and the reflecting plane, plus eight cases through the complete water/puddle ray marchers. They retain valid reflections with normal and DH depths. Another 96 renders run the actual composite pass with DH off/on, checking brightness response, contrast, black/white endpoints and average tone preservation. There are 199 rendered scenarios in total. Cloud renderer selection was checked against the installed Iris 1.11.4 property parser.

## Pending in-game checks

- With alpha.5 selected, compare Brightness 0.0, 0.5 and 1.0 at night, keeping Contrast at 1.0. Check texture detail on nearby and distant terrain, torches, water, caves, daytime and rain.
- Compare Shadow Darkness 0.0 and 0.4 on blocks and water; also check entity and block-entity shadows.
- Visit the Nether and End and switch dimensions; measure performance on the target GPU.

LODs use simplified colors and materials; DH's optional texture atlas is not integrated. Focusing on LODs does not have the temporal smoothing that Iris provides for normal terrain. Lighting/water continuity and the performance cost of effects still need to be evaluated in the game.

To diagnose failures, provide the Iris error or `logs/latest.log`, the pack settings, and a screenshot of the issue.

## References and credits

- Original shader: [Yamashita Shimejize](https://modrinth.com/shader/yamashita-shimejize), by rindefault; derived from Miniature Shader. Its Modrinth listing declares the MIT license. This fork preserves the original files and their attribution.
- [Iris's Distant Horizons interface](https://shaders.properties/current/reference/mod-support/distant_horizons/).
- [Iris for 26.2](https://github.com/IrisShaders/Iris/tree/26.2), particularly `DepthTransformer`, `DHTerrainTransformer`, and `DHCompat`.
