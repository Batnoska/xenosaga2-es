# Glosario y criterios de traducción

Español neutro latinoamericano (tú/ustedes, nunca vosotros). Los borradores se cargan como
"fuzzy" (sin revisar) y cada línea la aprueba una persona.

## Criterios

- **Terminología:** se usa la del material oficial en español cuando existe (Xenoblade
  Chronicles 2, que es español de España). Si no hay versión oficial, los términos propios de
  la saga quedan en inglés como en el Episode I (Gnosis, Realian, U.M.N., U-DO, Zohar...) y lo
  descriptivo se traduce (Segunda Miltia, Fundación Kukai).
- **Dudas de sentido:** cuando una línea del inglés suena rara, se contrasta con el japonés.
- **Nombres de quien habla:** se traducen una vez en `traduccion/nombres.po` y el juego los
  aplica a todos los diálogos.
- **Códigos:** no tocar `$zoom13;`, `$col…;` ni los botones `<○>`, `<□>`, `<△>`, `<×>`.
- **Subtítulos de video:** cada entrada es un tramo de frase sincronizado con la voz. La
  traducción se reparte en los mismos tramos, aunque haya que reordenar la frase. Máximo
  2 líneas y unos 50 caracteres por línea. Si el tramo dura poco, la traducción no tiene que
  ser más larga que el inglés. Al importar, los subtítulos que no alcanzan a leerse se quedan
  un poco más en pantalla cuando después hay silencio (`Subtitles.lengthen`).
- **Diálogos de campo:** sin saltos de línea; el juego los acomoda solo.
- **Puntuación:** ¿? y ¡! de apertura; comillas rectas "como en el original". En los
  diálogos no se copia la raya del inglés (―): una frase cortada termina en puntos
  suspensivos ("Es que...") y un inciso va entre comas. La raya queda para separar partes de
  un nombre o rótulo ("Miedo - Nivel 1") y en las firmas de los carteles.

## Términos oficiales (Xenoblade Chronicles 2 en español)

| Inglés | Español | Fuente |
|---|---|---|
| Encephalon | Encéfalo | habilidad de KOS-MOS en XC2 ("Encephalon" → "Encéfalo") |
| Hilbert Effect | efecto Hilbert | especial de KOS-MOS ("H-Effect R" → "Efecto Hilbert R") |
| Phase Transition | Transición de fase | habilidad de KOS-MOS y T-elos |
| R-Blade, X-Buster | R-Blade, X-Buster | especiales de KOS-MOS (igual que en inglés) |
| F-G Shot | Tiro F-G | especial de KOS-MOS |
| Ether | éter | XC2 ("Ether Cannon" → "Cañón de éter") |
| Mental Arithmetic | Cálculo mental | competencia de KOS-MOS |
| Imaginary / Real (MOMO) | imaginaria / real | Nintendo España, MOMO en XC2 Switch 2 Edition |

**Cambios respecto del Episode I** (donde quedaban en inglés): *Encephalon* pasa a **Encéfalo**
y *Ether* pasa a **éter**. Ninguno es brusco: son palabras comunes del español y no chocan
con los términos que siguen en inglés.

## Términos de la saga (sin versión oficial)

| Inglés | Español | Nota |
|---|---|---|
| Gnosis, Realian(s), U.M.N., U-DO, Zohar | igual | los Realians, un Realian |
| KOS-MOS, MOMO, chaos, Jr. | igual | chaos siempre en minúscula |
| E.S., A.G.W.S., A.M.W.S., U.R.T.V. | igual | |
| Y-Data | Y-Data | "los Y-Data" |
| Zohar Emulator | emulador del Zohar | |
| Proto Merkabah, Ormus, Durandal, Elsa, Dämmerung, Labyrinthos | igual | nombres propios |
| Second Miltia / Old Miltia | Segunda Miltia / Antigua Miltia | |
| Miltian (Conflict) | miltiano (Conflicto de Miltia) | |
| Federation / Federal Government | Federación / Gobierno Federal | |
| Kukai Foundation | Fundación Kukai | |
| Immigrant Fleet | Flota de Inmigrantes | |
| U-TIC Organization | Organización U-TIC | |
| Vector Industries | Vector Industries | First/Second Division → Primera/Segunda División |
| Abel's Ark | Arca de Abel | |
| Song of Nephilim | Canción de Nephilim | |
| 100-Series (Observational Realian) | Serie 100 | Mass-Produced → producida en masa |
| Imaginary Number Domain | dominio de los números imaginarios | derivado de "imaginaria" (MOMO en XC2) |
| GS (Global Samaritan) Campaign | Campaña SG (Campaña Samaritana Global) | femenino: la Campaña SG |
| GS Path | Ruta SG | femenino: la Ruta SG, una Ruta SG; "Path No. 01" → "Ruta n.º 01" |
| Civilian Agent | Agente Civil | |
| Segment File | Archivo de Segmento | la terminal portátil; pestaña "Segmentos", cartel "SEGMENTOS" |
| Segment Address | Dirección de Segmento | "Segment Address No. 01" → "Dirección de Segmento n.º 01" |
| Restricted Area / Submerged City | Zona restringida / Ciudad sumergida | como en el menú de lugares, también en diálogos y carteles |
| Our Treasure (hotel/posada) | Our Treasure | no se traduce; "Vault Key" → "Llave de caja fuerte" |
| Lavare | tintorería Lavare | no "lavandería" |
| maid (uniform) | sirvienta (uniforme de sirvienta) | no "mucama"; los objetos: "Uniforme azul/rosa/negro/celeste" |
| Miss Miltia posters | pósteres de Miss Miltia | no "carteles" |
| Dr. / Dra. | doctor / doctora en escenas de campo | abreviado solo en subtítulos, cinemáticas y GS, por espacio |

## Trato y voz

| Quién → a quién | Trato |
|---|---|
| KOS-MOS → todos | usted, registro formal; KOS-MOS en femenino |
| Shion → KOS-MOS, Allen, Jr., MOMO | tú |
| Allen → Shion | tú, la llama "jefa" |
| Mary y Shelley → Jr. | usted; "Little Master" → "joven amo" |
| Personal de la Fundación → Gaignun | usted; "Master Gaignun" → "amo Gaignun" |
| Jr. | tú con todos, tono canchero |
| MOMO | educada; "señor/señora" con adultos que no son del grupo |
| Juli Mizrahi, Helmer | registro formal |
| Jin ↔ Canaan, Jin ↔ Shion, Jin → chaos | tú (en el flashback de hace 14 años, usted: recién se conocen) |
| Helmer → Canaan, Jr. | tú; Canaan → Helmer: usted |
| Jin ↔ Helmer | usted los dos ("teniente general", "capitán") |
| Juli ↔ Ziggy | usted los dos ("Dra. Mizrahi", "Jan Sauer") |
| Tripulación del Elsa → Matthews | usted, "capitán" |
| Margulis → Patriarca | usted, "Su Santidad"; el Patriarca lo tutea |
| Margulis → Pellegri | tú; Pellegri → Margulis: usted |

### Cómo habla cada uno

Criterio general: que suene a gente hablando, no a traducción. Se reacomoda la frase cuando
el calco del inglés queda rígido; los modismos van con moderación y solo en personajes que
los justifican (Jr., Matthews, Tony, la tripulación, algunos NPC), siempre entendibles en toda
Latinoamérica (nada de "che", "güey", "chamo" ni "vosotros").

- **Shion:** cálida, directa, a veces impaciente o terca; con Allen, mandona sin ser cruel;
  con Jin, la hermana menor que se fastidia ("¡Hermano!"). Habla normal, sin rebuscar.
- **KOS-MOS:** usted, frases completas, vocabulario técnico, sin muletillas ni exclamaciones.
  Informa más de lo que conversa ("Afirmativo", "Entendido").
- **Allen:** nervioso, se atropella, se disculpa; dice "jefa" a Shion. Puede titubear ("e-eh").
- **Jr.:** canchero, seguro, burlón; frases cortas, algo de jerga ("¡A darle!", "tranquilo",
  "ni loco"), sin pasarse. Cuando habla en serio (con Gaignun, de Albedo) baja el tono.
- **Gaignun:** sereno, formal, medido. Nunca jerga.
- **Ziggy:** seco, militar, frases cortas ("Entendido", "Negativo"); muy protector con MOMO.
- **MOMO:** educada, dulce, entusiasta; "señor/señora" con adultos que no son del grupo.
- **chaos:** tranquilo, amable, enigmático; habla simple y con calma.
- **Jin:** de pocas palabras, irónico con Shion, solemne en combate; registro algo culto.
- **Canaan:** varón (Realian de combate; la wiki lo confirma), soldado sobrio y leal a Helmer;
  seco con quien no conoce. En el flashback de hace 14 años, Canaan y chaos tratan de usted a
  Jin, que recién conocen, y Jin les habla de usted también.
- **Helmer:** autoridad paternal, formal.
- **Juli Mizrahi:** científica, fría y precisa; se quiebra al hablar de Sakura.
- **Albedo:** teatral, burlón y desquiciado; cambia de tono de golpe, se ríe, se regodea
  ("hermanito"); puede ser grosero sin llegar a lo vulgar.
- **Margulis:** fanático, solemne, grandilocuente; desprecia a los demás ("insectos").
- **Sergius (Patriarca) y Pellegri:** solemnes y fríos; Pellegri, cortante.
- **Matthews:** capitán bruto y gruñón, insulta con cariño ("¡Inútiles!"), "¡Maldita sea!".
- **Tony:** piloto acelerado, jerga de barrio suave. **Hammer:** técnico tímido y nervioso.
- **Profesor:** científico excéntrico, se entusiasma y se va por las ramas. **Scott:** su
  asistente, paciente y exasperado ("¡Profesor!").
- **Mary y Shelley:** educadas con Jr. ("joven amo"); Mary más suelta, Shelley más formal.
- **Vecinos de la Fundación:** a Jr. lo tratan de usted ("joven amo"); a MOMO, "pequeña"; al
  resto del grupo, tú/ustedes. Si el inglés no marca el género de quien lidera el grupo, la
  frase queda neutra ("Relájate", no "Tranquilo").
- **Máquinas, carteles y cerraduras:** usted impersonal ("Ingrese la contraseña").

Palabras y giros a evitar por regionales: "No hay caso", "nomás", "¡Dale!", "recién" como
adverbio ("apenas"), "seguido" por "a menudo", "en lo de" (por "en la casa/tienda de"),
"reto/retar" (por "regaño"), "darse vuelta", "Buen día", "no cierra", "tontorrón", y las
muletillas "Digo" o "Este" para "Um" ("digo" sí vale para corregirse: "Eh, digo..."). Tampoco
"sí o sí", "cloacas" (mejor "alcantarillas") ni "calar" (por "descubrir"). Para los
hijos pequeños, "niños" mejor que "chicos"; las fotos se "toman". Ojo con los dobles
sentidos: "anillo vibratorio", no "vibrador". Bonny es "superladrona"; la "slump" de
Margoyles, una "crisis creativa".

## Combate y menús

Criterio para los nombres de habilidades, éteres, técnicas y Ataques Dobles: se traduce lo
descriptivo (como hace Xenoblade en español) y quedan en inglés los nombres inventados, las
siglas y los nombres oficiales (Medica, Refresh, XSB/XBK, Erde Kaiser, X-BUSTER,
los "Buster", HP Mind, Break B10, STR+2…). Las abreviaturas de parámetros (Str, Vit, Dex, Eva,
Agl, Eatk, Edef, EXP) quedan igual porque también salen en gráficos; C.Pt y S.Pt pasan a
PC y PH (puntos de clase y de habilidad), y Lv a Nv, también en los gráficos.

| Inglés | Español | Nota |
|---|---|---|
| Strike / Pierce / Slash | Golpe / Perforación / Corte | tipos de daño |
| Beam / Fire / Ice / Thunder / Aura | Haz / Fuego / Hielo / Rayo / Aura | |
| L/H Poison, Blind, Slow, Weak, Heavy, Stun, Bind | Veneno, Ceguera, Lentitud, Debilidad, Pesadez, Aturdimiento, Atadura + L/H | "Lentitud L" |
| H Stop / H Lost / Charge Down / Boost Lock | Inmovilidad H / Pérdida H / Menos carga / Bloqueo de Boost | Lost Guard → Antipérdida |
| Down Dex / Force / P Def / Ether / E Def | Bajar Destreza / Fuerza / Def. física / At. éter / Def. éter | éteres que bajan parámetros |
| Break Sensors / Arms / Armor / Beam / Shield | Romper sensores / armas / blindaje / haz / escudo | ídem, contra enemigos M |
| Double Attack | Ataque Doble | |
| Boost, Stock, Counterboost | igual | aparecen en gráficos en inglés del combate |
| Break / Air / Down (estados) | Desequilibrio / Elevación / Derribo | elegido por el usuario (2026-10-26); "Break B10" → "Desequilibrio B10" |
| Secret Key / Decoder | Llave Secreta / Decodificador | |
| Veil / Wall / Sword | Velo / Muro / Espada (de llamas, hielo, rayo, aura) | éteres |
| Blast / Storm / Burst | Ráfaga / Ciclón / Estallido (ígnea, gélida, de rayo, de aura) | éteres |
| Coat (habilidad) / Guard | Manto / Anti- ("Antiveneno", accesorios "G Antiveneno") | |
| Med Kit / Ether Pack / Rejuvenator / Revive | Botiquín / Kit de éter / Elixir / Reanimador | objetos |
| Psycho Pocket / Safety Level / Best Ally | Hurto psíquico / Nivel seguro / Mejor aliado | |
| Event Slot | casilla de evento | |
| Class Points / Skill Points | Puntos de clase / Puntos de habilidad | minúscula, como "Puntos de experiencia" |
| Short / Long (alcance) | Cerca / Lejos | igual en el menú y en las descripciones de técnicas |
| Partner (Ataque Doble) | Aliado | |
| Vessel of Anima | Vasija de Anima | |
| Chief Inquisitor | Gran Inquisidor | Margulis |
| Fifth Jerusalem | Quinta Jerusalén | |
| memory card (8MB) (for PlayStation®2), MEMORY CARD slot | tarjeta de memoria (8MB) (para PlayStation®2), ranura de MEMORY CARD | términos de Sony |

### Rótulos dibujados en texturas (tools/graficos.py)

| Inglés | Español | Dónde |
|---|---|---|
| STOCK / ETHER / ITEM / DOUBLE | STOCK / ÉTER / OBJETO / DOBLE | comandos de combate |
| CHANGE / SPECIAL / ESCAPE / MOVE | CAMBIO / TÉCNICA / HUIR / MOVER | comandos de combate (TÉCNICA como el encabezado "TECNICA") |
| C.Pt / S.Pt / Lv / Next Lv | PC / PH / Nv / Sig. Nv | ficha de estado |
| Items / Ether / Skills / Tech | Objetos / Éter / Habilid. / Técnicas | pestañas del menú |
| Status / Party / GS Path / Segment F / Options | Estado / Grupo / Ruta SG / Segmentos / Opciones | pestañas del menú (U.M.N. queda) |
| << Items / Ether / Skills / Party / Equip >> | << Obj. / Éter / Habil. / Grupo / Equip. >> | rótulos de obj01 (abreviados para que entren) |
| << Attack Data / Learned / Accessories >>, Caster | << Datos / Aprend. / Accesorios >>, Usuario | rótulos de obj01 |
| COMBATANT / RESERVE | COMBATE / RESERVA | carteles de la pantalla del grupo |
| << COMBATANT >> / << RESERVE >> (paneles 3D) | << COMBATE >> / << RESERVA >> | pantalla del grupo (yosikawa/model/atk.txy, rsv.txy) |
| GS PATH (cartel) | RUTA SG | Ruta SG (g2_01; se espejan las cápsulas) |
| Entrance / Result / Citizen Profile / Exit | Entrada / Logros / Ciudadano / Salir | Ruta SG (g2_01) |
| Message from Client / Procurator, << Back, Next >> | Mensaje del cliente / del procurador, << Atrás, Sig. >> | Ruta SG (g2_01) |
| Achievement / Citizen Profiles | Logros / Ciudadanos | botones de la entrada de la Ruta SG |
| SEGMENT FILE (cartel) | SEGMENTOS | Archivo de Segmento (seg01; baldosas sueltas, x corridas en el ejecutable) |
| NO DATA / IN PROGRESS / COMPLETE!! | SIN DATOS / PENDIENTE / ¡COMPLETO! | Archivo de Segmento (seg01) |
| Segment Address / Treasure Details | Dirección / Datos del tesoro | Archivo de Segmento (seg01) |
| SUCCEEDED! / FAILED! / IN PROGRESS / NO DATA / NEW! | ¡LOGRADA! / ¡FALLIDA! / PENDIENTE / SIN DATOS / NUEVA | estados de la Ruta SG (g2_02; femenino, por la Ruta n.º NN) |
| OPEN : (globo de los mensajes) | ABRIR : | Ruta SG (g2_02) |
| Break Block / Air Block / Down Block | Sin Desequilibrio / Sin Elevación / Sin Derribo | carteles del combate (stat.xtx) |
| Hi-Critical / Critical / SkillPoint x / Zone A / Intercept | Súper Crítico / Crítico / Ptos. hab. x / Zona A / Intercepción | carteles del combate |
| Turn Cancel / Beam / Back Hit | Turno anulado / Haz / Por detrás | carteles del combate |
| Thunder / Fire / Ice / Aura | Rayo / Fuego / Hielo / Aura | carteles del combate ("AC" queda) |
| Bonus / Evasion / Guard | Extra / Evasión / Defensa | carteles del combate |
| PLAYER / ENEMY, ZONE, MENU | ALIADO / ENEMIGO, ZONA, MENÚ | rótulos chicos del combate (CURRENT y -SELECT- quedan) |
| FRONT / SELECT / BACK | FRENTE / SELECT / ATRÁS | elección de zona en el combate (SELECT es el botón) |
| NO DATA / Class / Level / Skill / Caster | SIN DATOS / Clase / Nivel / Habil. / Usuario | rótulos de 4 bits de font.xtx |
| pantalla de controles (ctrl01) | Botones L2/R2, Joystick izquierdo, Cambiar categoría, Girar el navegador de habilidades… | yosikawa/ctrl01.xtx |
| NEW GAME / CONTINUE / INSTALL / UNINSTALL / EXIT / THEATER | NUEVA PARTIDA / CONTINUAR / INSTALAR / DESINSTALAR / SALIR / TEATRO | menú del título (titleobj.xtx, ARX) |
| DISC 1 / DISC 2 | DISCO 1 / DISCO 2 | logo del título (title.bin, title2.bin, ARX) |
| GAME OVER / TO BE CONTINUED | FIN DEL JUEGO / CONTINUARÁ | yajima/gameov1.jpg, end.jpg |
| - CENTER -, accept / cancel / default | – CENTRO –, aceptar / cancelar / inicial | ajuste de pantalla (yajima/mnt_set.jpg) |
| MEMORY CARD slot 1 | MEMORY CARD 1 | el encabezado "Cargar / …" tiene 32 bytes |
| L O A D / S A V E (cartel) | C A R G A R / G U A R D A R | pantalla de cargar/guardar: baldosas de seg01; el código se cambió por un bucle (graficos.save_load_code) |
| Page / Loading... / button: Start | Pág. / Cargando... / Empezar | páginas de la Ruta SG; pantalla de la historia |
| The Story So Far: | La historia hasta ahora: | resúmenes (traduccion/imagenes/sinopsis.po) |

U.M.N. queda como nombre propio en textos y pestañas.
GS se traduce como SG porque el juego lo explica ("Global Samaritan"). En la Ruta SG, Ukun (el procurador) habla en masculino ("a guy like me").
