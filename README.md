# Xenosaga Episode II en español

Traducción al español latinoamericano neutro de *Xenosaga Episode II: Jenseits von Gut und Böse*
(PlayStation 2, versión americana NTSC-U, dos discos).

Está traducido todo el texto del juego:

- diálogos, subtítulos de los videos, menús, combate y tutorial;
- la Ruta SG y el Archivo de Segmento;
- los gráficos con texto: menú del título, carteles del combate, pantalla de controles,
  "La historia hasta ahora" y otros.

**Estado:** beta 0.9. Se puede jugar completo, pero todavía se está probando en PCSX2.

## Para jugar

Descarga el kit de la sección [*Releases*](https://github.com/Batnoska/xenosaga2-es/releases)
y sigue su `LEEME.txt`. En resumen: abre
`Aplicar parche.exe` y elige las ISO de tu copia del juego. Para Linux, Mac o Steam Deck hay una
versión en Python.

El parche no incluye el juego ni archivos del juego: guarda solo las diferencias con los
archivos originales, y comprueba que tus ISO sean las esperadas antes de escribir nada.

## Qué hay en el repositorio

| Carpeta | Contenido |
|---|---|
| `traduccion/` | La traducción en archivos `.po` (inglés original y español), uno por escena, mapa, menú o video. Se pueden editar con Poedit. |
| `tools/` | Las herramientas: extraer e importar textos, formatos del juego, gráficos, el parche y el kit de publicación. |
| `tools/aplicador/` | El aplicador de Windows (C#) y la plantilla del `LEEME.txt`. |
| `docs/` | Glosario y criterios de traducción, lista de pruebas en el juego, notas de cada tanda de trabajo e ideas para un parche de mejoras. |
| `work/` | Solo los scripts de revisión y control. Lo demás que se genera ahí (lo extraído del juego, las ISO, el kit) no se sube. |

Los criterios de la traducción, los términos y cómo habla cada personaje están en
[docs/glosario.md](docs/glosario.md).

## Armar las ISO desde el código

Hace falta:

- Windows, porque los gráficos se dibujan con fuentes que vienen con Windows (Arial Black,
  Bahnschrift, Century Gothic, Courier New y Segoe UI);
- Python 3.12 o posterior, con `pip install -r requirements.txt`;
- las dos ISO originales de la versión NTSC-U (sirven también las del undub).

Pasos:

1. Copia `iso_path.ejemplo.txt` como `iso_path.txt` y escribe las rutas de tus ISO, una por
   disco.
2. Arma las ISO traducidas en `work/`:

   ```
   python tools/textos.py importar
   ```

3. Comprueba los gráficos y el GS. El control del GS necesita antes extraer sus textos
   originales:

   ```
   python work/verificar_graficos.py
   python tools/x2iso.py extract 0 work/extract/0 --match "iwase/*"
   python work/verificar_gs.py
   ```

4. Arma el kit de publicación en `work/publicar/`. Con `--probar` también aplica el parche a
   tus ISO y compara el resultado:

   ```
   python tools/kit.py 0.9-beta --probar
   ```

Para corregir textos se editan los `.po`, o se cargan lotes de borradores con
`python tools/borrador.py lote <archivo>`, y se revisan con
`python tools/borrador.py revisar <carpeta>`. Esta última avisa de textos que no entran en su
recuadro.

## Reportar errores

En las [*Issues*](https://github.com/Batnoska/xenosaga2-es/issues) de este repositorio, o por
Discord a @argolla. Una captura y dónde estabas en
el juego ayudan mucho.

## Créditos

- **Batnoska:** traducción, revisión, gráficos y herramientas.
- Con la ayuda de Claude (Anthropic), un asistente de inteligencia artificial.

## Licencia

El código y la traducción se publican con la licencia MIT ([LICENSE](LICENSE)). La licencia no
cubre el juego ni sus textos originales en inglés, que aparecen junto a la traducción en los
`.po`.

Xenosaga es una marca de Bandai Namco Entertainment. El juego fue desarrollado por Monolith
Soft. Este es un proyecto de fans, sin fines de lucro y sin relación con esas empresas.
