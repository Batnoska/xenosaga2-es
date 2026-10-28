XENOSAGA EPISODE II: SPANISH TRANSLATION AND DEFINITIVE EDITION
Version {version} ({fecha})
================================================================

This program applies two fan patches to "Xenosaga Episode II: Jenseits von Gut und
Böse" for PlayStation 2, together or separately:

- The Spanish translation (Latin American neutral Spanish): the whole game, including
  dialogue, video subtitles, menus, battles and the graphics with text.
  https://github.com/Batnoska/xenosaga2-es

- The Definitive Edition: an optional patch that tackles what players have criticized
  the most since 2004: regular battles that drag on, slow progression, skills locked
  behind Secret Keys and Double Techs that are not worth their cost. It does not
  redesign the game: every change is an option.

Both are betas. If you find a problem, see "Reporting bugs".


WHAT YOU NEED
-------------
- The ISOs of your copy of Xenosaga Episode II, US version (NTSC-U): disc 1
  (SLUS-20892) and disc 2 (SLUS-21133). Undub ISOs (Japanese voices) made from that
  version work too.
- About 4.7 GB of free space per disc.
- Windows 7 or later. For Linux, Mac or Steam Deck, see "Other systems".

The patch does not include the game: you need your own ISOs. If your copy is in
another format (CHD, CSO, BIN/CUE), convert it to ISO first.


HOW TO APPLY IT ON WINDOWS
--------------------------
1. Open the patcher (".exe").
2. At the top there are two boxes: "DEFINITIVE EDITION" and "SPANISH TRANSLATION".
   Check what you want to apply. The gear next to the Definitive Edition opens its
   options.
3. Drag the original ISOs onto the window, or click "DISC 1" and "DISC 2" to choose
   them. The program recognizes each disc and tells you if an ISO is not the right
   one.
4. Click "APPLY PATCH" and wait until it finishes (a few minutes per disc).

A new ISO is created next to each one, ending in " (Definitive)", " (Spanish)" or
" (Spanish + Definitive)". The original ISOs are not modified.

Before writing anything, the program checks that every file it replaces is the
original one. If it is not (another version of the game, or an ISO with another
patch), it warns you and changes nothing. When it finishes, it verifies the new ISO.

The window plays music. The "MUSIC" button (or the M key) raises the volume in five
steps and then turns it off. The window follows the language of Windows; use the
flags at the top to switch between English and Spanish.

If Windows shows "Windows protected your PC", click "More info" and then "Run
anyway". That warning appears with any program without a digital signature.


DEFINITIVE EDITION
------------------
There are four profiles, and from the gear you can turn each change on or off:

- Original: the game as released.
- Comfort: original battles with less grind (no Secret Keys, more item drops,
  stronger healing and the Japanese debt).
- Definitive (recommended): shorter regular battles with more ways to win,
  smoother progression, and bosses just as challenging, with Break patterns of
  three hits at most.
- Story: everything in Definitive, turned up, plus bosses with less HP.

Changes marked "TESTING" were worked out from the game data but have not been seen
working in a playthrough yet. The lower debt only shows in saves where the debt has
not appeared yet.

The battle data of the game was researched by TheSparda (Xenosaga-2-Editor).


OTHER SYSTEMS (LINUX, MAC, STEAM DECK)
--------------------------------------
You need Python 3. Open a terminal in the folder whose name ends in "(Python)" and
run this command for each disc, changing the file names:

  python3 parche.py aplicar xenosaga2_es.zip "Disc 1.iso" "Disc 1 (Definitive).iso" --sin-traduccion --perfil definitiva

Without --sin-traduccion it also applies the Spanish translation; without --perfil,
only the translation. Profiles: original, comodidad (Comfort), definitiva
(Definitive), historia (Story). --opcion adjusts a single change (for example
--opcion deuda=0). It does exactly the same as the Windows program.


HOW TO PLAY
-----------
Load the new ISOs in PCSX2 like any other game. At the end of disc 1, switch to the
new ISO of disc 2. Tested on PCSX2; not tested on a real PS2 yet.


REPORTING BUGS
--------------
Take a screenshot, write down where you were and what happened, and send it:
- On GitHub: https://github.com/Batnoska/xenosaga2-es/issues
- On Discord to @argolla.


CREDITS
-------
Batnoska: Spanish translation, Definitive Edition, graphics and tools.
With help from Claude (Anthropic), an AI assistant.
Battle data research: TheSparda (Xenosaga-2-Editor, MIT license).
Patcher music: "The Image Theme of Xenosaga II", by Yuki Kajiura.

Xenosaga is a trademark of Bandai Namco Entertainment. The game was developed by
Monolith Soft. These patches were made by fans, non-profit and unrelated to those
companies. No game files are distributed, only the differences the patch applies.
The patcher window uses the game's logo, promotional art (Jr., Albedo and the Zohar)
and music as a tribute; they belong to their owners.
