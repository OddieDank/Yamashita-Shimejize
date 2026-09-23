# Yamashita Shimejize — Minecraft 26.2 + Distant Horizons

Adaptación experimental de [rindefault/Yamashita-Shimejize](https://github.com/rindefault/Yamashita-Shimejize), basada en el commit `e5f709fd149bf26f5c5d60ae8481b001fcac279a`.

**Estado: alpha. Compilación GLSL y pruebas de profundidad verificadas; pendiente de validación visual dentro de Minecraft.** No es una versión oficial del autor original.

## Entorno objetivo

- Minecraft Java **26.2**, Fabric y renderizado **OpenGL**.
- Iris **1.11.4+mc26.2** y la versión de Sodium requerida por Iris (0.9.2).
- Distant Horizons **3.3.2-26.2-fabric-neoforge**.
- DH debe usar su renderizador OpenGL, no Blaze3D. También se comprueba la compilación sin DH.

Esto adapta el shaderpack; no modifica los JAR de Minecraft, Iris o DH. No añade soporte Vulkan.

## Instalación

1. Ejecutar `python3 tools/build_pack.py` o usar el ZIP generado en `dist/`.
2. Copiar `Yamashita-Shimejize-mc26.2-DH-alpha.1.zip` a la carpeta `shaderpacks` de la instancia.
3. Seleccionarlo en Iris. El ZIP contiene `shaders/` directamente en su raíz.
4. Empezar con el perfil LOW o NORMAL, una distancia normal de 8–12 chunks y DH en 128 chunks. Ajustar según el rendimiento.

Las sombras proyectadas por los LOD se activan con **Distant Horizons shadows** en las opciones de iluminación. Están desactivadas inicialmente para limitar el coste. La iluminación solar y las sombras cercanas existentes permanecen disponibles.

## Cambios

- Programas `dh_terrain`, `dh_water` y `dh_shadow` para Overworld, Nether y End.
- Reutilización de la iluminación, niebla, materiales emisivos y salidas de agua del shader original; los LOD usan el color que entrega DH.
- Comparación de las posiciones reconstruidas con cada proyección, en lugar de comparar profundidades de rangos diferentes.
- Profundidad compartida para nubes, reflejos, desenfoque de movimiento, profundidad de campo, bloom, calor y oclusión de efectos del cielo.
- Niebla ajustada a la distancia de DH tanto en terreno cercano como lejano.
- Recorte del agua/terreno DH detrás de geometría normal y mezcla independiente de normales e identificadores del agua.
- Declaraciones explícitas de matrices ausentes en los programas originales que usan las funciones comunes de transformación.

Iris 1.11.4 convierte las lecturas de profundidad y las posiciones para el renderizado con profundidad invertida de 26.2. El pack mantiene la convención de profundidad que Iris expone a los shaders; no invierte los valores una segunda vez.

## Validación reproducible

En Linux con Python 3 y Mesa EGL/OpenGL instalados:

```sh
python3 tools/check_shaders.py
python3 tools/test_scene_depth.py
python3 tools/build_pack.py
```

La comprobación GLSL compila y enlaza 300 pares de programas, cubriendo las carpetas de dimensiones, DH activado/desactivado y opciones predeterminadas/reducidas. Expande includes, proporciona macros/atributos de Iris y adapta algunas convenciones para el compilador independiente. **No ejecuta el transformador Java de Iris ni sustituye una prueba en el juego.**

La prueba de profundidad ejecuta el GLSL real del resolvedor en un framebuffer flotante con siete escenas sintéticas: superficies cercanas, superficies DH, solapamientos, geometría próxima al límite lejano y cielo. Incluye un caso donde comparar los valores de profundidad directamente elegiría la superficie equivocada.

## Comprobación pendiente en el juego

- Cargar y recargar el pack sin errores, primero con DH apagado y después activado.
- Volar por la transición entre chunks normales y LOD; comprobar iluminación, huecos y niebla de día, de noche y con lluvia.
- Observar océanos, costas, agua desde debajo de la superficie y montañas delante/detrás de nubes.
- Probar reflejos, DOF, movimiento de cámara y sombras DH opcionales.
- Visitar Nether y End y cambiar de dimensión; medir el rendimiento en la GPU de destino.

Los LOD usan colores y materiales simplificados; no se incorpora el atlas de texturas opcional de DH. El enfoque sobre LOD no dispone del suavizado temporal que Iris proporciona para el terreno normal. La continuidad exacta de iluminación/agua y el coste de los efectos todavía deben evaluarse en el juego.

Para diagnosticar fallos, adjuntar el error de Iris o `logs/latest.log`, las opciones del pack y una captura del problema. No incluir tokens ni datos de cuenta.

## Referencias y créditos

- Shader original: [Yamashita Shimejize](https://modrinth.com/shader/yamashita-shimejize), por rindefault; derivado de Miniature Shader. Su ficha en Modrinth declara licencia MIT. Este fork conserva los archivos originales y no cambia su atribución.
- [Interfaz Distant Horizons de Iris](https://shaders.properties/current/reference/mod-support/distant_horizons/).
- [Iris para 26.2](https://github.com/IrisShaders/Iris/tree/26.2), especialmente `DepthTransformer`, `DHTerrainTransformer` y `DHCompat`.
