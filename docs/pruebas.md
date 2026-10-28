# Lista de pruebas en el juego

Ordenada por riesgo: lo de arriba toca código o nunca se vio en pantalla. No hace falta jugar
todo de corrido; con partidas guardadas en los puntos clave alcanza.

## Antes de empezar

- [ ] **Arma las ISO con el kit de publicación, como lo haría cualquier jugador:**
  - Abrí `Aplicar parche.exe` y elegí las dos ISO originales (arrastrándolas o con clic en
    cada disco).
  - Jugá con las ISO que genera, no con las de `work/`, así se prueba el parcheador también.
- [ ] **La ventana del aplicador:**
  - la música arranca bajita y el botón MÚSICA la sube de a un nivel hasta apagarla;
  - los sonidos de los botones, el arrastre de la ventana, minimizar y cerrar;
  - una ISO que no es del juego (cualquier otra) tiene que marcarse como NO VÁLIDA;
  - cerrar a mitad de un parche tiene que preguntar, y si cancelás, no tiene que quedar una
    ISO a medio crear;
  - si ya existe la ISO en español, tiene que preguntar antes de reemplazarla.
- [ ] **La Definitive Edition en el aplicador:**
  - las dos casillas de arriba se marcan y desmarcan; sin ninguna, el botón dice ELIGE QUÉ
    APLICAR;
  - el engranaje abre la configuración: los perfiles, las casillas, las flechas ‹ › de cada
    nivel, el detalle al pasar el ratón, PERSONALIZADA cuando tocás algo, RESTABLECER, LISTO
    y Esc;
  - las banderas pasan toda la ventana a inglés o a español (también la configuración y los
    mensajes);
  - la frase de abajo del logo: en alemán al abrir, se descifra mientras se aplica la
    traducción y queda en español con brillo al terminar; con solo la Definitive Edition queda
    en alemán;
  - una ISO ya traducida con esta versión y solo la Definitive Edition marcada: el botón se
    habilita y crea la ISO terminada en "(Definitive)".
- [ ] **En el juego, con las tres opciones "en prueba" activadas a mano** (no vienen en ningún
  perfil hasta que se prueben):
  - Ice Brand pide 1 de Stock en vez de 2;
  - First Combo se puede comprar sin la Llave secreta 16;
  - la deuda de la Campaña SG es de 1.000.000 (solo en una partida en la que todavía no
    apareció).
- [ ] Guardá en la tarjeta de memoria en estos puntos, para volver rápido después de cada
  corrección: antes del primer combate, al llegar a la Fundación, en el Dämmerung, y antes
  del cambio de disco.
- Para reportar algo: una captura, dónde estabas y qué esperabas ver. Si es un texto cortado,
  basta con la captura.

## 1. Lo más delicado (toca código del juego)

- [ ] **Guardar y cargar:**
  - el cartel de arriba a la derecha (C A R G A R / G U A R D A R);
  - "/ Nv" en las ranuras;
  - el nombre del lugar en la lista de partidas. Guardá en el Dämmerung, frente al cuarto de
    Shion: "Frente al cuarto de Shion" es el nombre de lugar más largo y puede cortarse.
- [ ] **Pantalla de título:**
  - el menú (NUEVA PARTIDA, CONTINUAR, TEATRO...) y "DISCO 1";
  - los mensajes sin tarjeta de memoria (sacala en la configuración de PCSX2).
- [ ] **Cambio de disco:** "Continuará" al final del disco 1, "Inserta el DISCO 2..." y qué
  pasa si se pone el disco equivocado.
- [ ] **Combate:**
  - los carteles de Desequilibrio, Elevación, Derribo, críticos, "Por detrás" y elementos;
  - ALIADO / ENEMIGO en el orden de turnos;
  - ZONA, la ficha MENÚ, y FRENTE / ATRÁS al elegir zona.

## 2. Textos del GS (cambiaron mucho y no se vieron en pantalla)

En el Archivo de Segmento, pestaña de la Ruta SG:

- [ ] La lista de misiones y el texto de cada una: que no se corte abajo y que las tildes,
  la ñ y los signos ¡¿ salgan bien. En el GS las tildes pasan por un conversor especial, así
  que es donde más pueden fallar.
- [ ] Los perfiles de los vecinos, y la ayuda de abajo ("Mira a quién conociste").
- [ ] Los tesoros y los logros (¡LOGRADA!, ¡FALLIDA!, PENDIENTE).
- [ ] La presentación de la Agente Bunnie: la segunda opción ahora dice "No trates a la gente
  como ratas de laboratorio".

## 3. Menús con textos al límite del ancho

- [ ] **Objetos clave:** "Llave Secreta 13" a "Llave Secreta 31", que son unos 25 px más
  anchas que el inglés. Miralas también al usarlas en la pantalla de habilidades.
- [ ] **Ataques Dobles:** que "Réquiem del arcángel" entre en la lista. En el detalle debe
  decir "Aliado", y en las técnicas el alcance debe decir Cerca / Lejos.
- [ ] **Habilidades:** "Clase", "Nivel" y "Habil.", y el tutorial de habilidades. Tiene tres
  líneas casi al límite: "Medica es una habilidad...", "Medica está en la clase A..." y
  "Hay objetos que aumentan los Puntos de habilidad...".
- [ ] **Éter:** "Usuario" no debe pisar nada a la derecha.
- [ ] **Extras del título:** la búsqueda de datos del Episode I y sus mensajes de tarjeta de
  memoria.

## 4. Diálogos que más cambiaron

- [ ] **Secundarias de la Fundación:**
  - los anillos y los gatitos de King;
  - piedra, papel o tijera con Johnny;
  - Bonny en el Ironman;
  - Caito y los uniformes de sirvienta en la tintorería Lavare;
  - los ratones de Dominic;
  - el juego de preguntas del hotel Our Treasure (con la Ficha de juego gratis).
- [ ] **Flashback de hace 14 años:** Canaan habla en masculino, y él, chaos y Jin se tratan
  de usted.
- [ ] **Listas de opciones en general:** cada opción debe salir en su propia línea, nunca dos
  juntas con una barra.

## 5. Si llegás

- [ ] **"La historia hasta ahora"** al cargar una partida: son 22 imágenes y la 07 cambió.
- [ ] **El final:** los créditos, "FIN DEL JUEGO" y el Teatro.

## Lo que ya sabemos que sigue en inglés (no hace falta reportarlo)

- CURRENT, -SELECT- y LEVEL UP!: no hay letras para armarlos o no encontré dónde se dibujan.
- Room, Standby, MainPilot y Copilot, en la pantalla de los E.S.
- Boost, Stock y Counterboost: quedan en inglés a propósito, porque así salen en los gráficos
  del combate.
- En el undub, los subtítulos usan los tiempos del doblaje en inglés, así que algunos
  aparecen cuando la voz japonesa ya va por la mitad de la frase. Es del undub, no de la
  traducción. Desde el 27/10 los que duran poco se quedan un poco más en pantalla.
