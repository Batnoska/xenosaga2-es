# Ideas para un parche de mejoras (para después de la traducción)

Lista de partida. Cada idea hay que investigarla (qué dice la comunidad, cómo está hecho en el
juego) antes de decidir si se hace. La factibilidad es una estimación con lo que ya sabemos del
formato de los archivos.

| Idea | Problema que resuelve | Dónde estaría | Factibilidad |
|---|---|---|---|
| Multiplicadores de EXP, Puntos de Clase y Puntos de Habilidad | progresión lenta, combates poco gratificantes | registros de enemigos en `yamamoto/batdat.us` (ya sabemos leerlo) | alta |
| Ajustar HP y defensas de enemigos con mucha vida | combates largos | mismo archivo | alta |
| Costos y cargas (Stock, Boost, EC del E.S.) | ritmo lento del sistema de zonas y Break | `batdat.us` y lógica del overlay `OV01.OVL` | media |
| Animaciones de combate más rápidas | la queja más común: combates lentos | código del combate (`OV01.OVL`), hay que investigarlo | baja/media |
| Resincronizar los subtítulos con el audio japonés | el undub usa los tiempos del doblaje en inglés | `movie/*/*.txt` (tiempos) + análisis del audio de cada video | media |
| Pantalla ancha | 4:3 | parches de pantalla ancha de PCSX2 (ver si ya existe uno) | a investigar |
| Misiones secundarias poco claras (Segment Address, decodificadores) | guías obligatorias | textos de pistas; quizá una guía incluida | alta (texto) |
| Errores conocidos del juego original | a relevar | según cada error | a investigar |
