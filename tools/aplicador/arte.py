"""Arte del aplicador de Windows: fondo, botones, sonidos, ícono y medidas de la ventana.

kit.py llama a generar() al armar el kit. La ventana usa renders oficiales del juego (Jr., Albedo y
el Zohar), el logo de Xenosaga Episode II y "The Image Theme of Xenosaga II" de Yuki Kajiura. Nada
de eso está en el repositorio:
  - los renders y el logo se descargan solos la primera vez a work/arte_externo/descarga (de la
    Xeno Series Wiki, comprobados por SHA-1);
  - el tema hay que copiarlo a mano como work/arte_externo/tema.mp3. Sin él, no hay música.

Las medidas son de diseño (una ventana de 760 x 470). Todo se dibuja al doble (S) y al final se
reduce al tamaño real de la ventana (E veces las medidas de diseño). Las medidas y E van a
Diseno.cs, que se compila con el aplicador.
"""
import hashlib
import io
import math
import os
import random
import struct
import urllib.request
import wave
import zipfile

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXTERNO = os.path.join(ROOT, "work", "arte_externo")
TEMA = os.path.join(EXTERNO, "tema.mp3")
FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
FUENTES = {
    "zohar": ("https://xenoserieswiki.org/w/images/8/88/Zohar_XS2.png", "7671c5d468d785e2ed90b8702a427fb110406f3e"),
    "jr": ("https://xenoserieswiki.org/w/images/a/af/Jr_XS2_2.jpg", "a219e382c8a3993d03a3cdeddebc5ea21b5af50a"),
    "albedo": ("https://xenoserieswiki.org/w/images/0/0d/Albedo_XS2.png", "42f9fd25ca5849ce57521a918dd9edd9d8f68241"),
    "logo": ("https://xenoserieswiki.org/w/images/b/b7/Xenosaga_II_logo.jpg", "0dff4c52c8abf77f85f4ac9a4b9ef96d91c89623"),
}

S = 2
E = 1.4  # la ventana real mide 1064 x 658: en 1920 x 1080 la de diseño quedaba chica
W, H = 760, 470
CYAN = (90, 220, 255)
VIOLET = (170, 120, 255)

# Medidas en píxeles de la ventana (x0, y0, x1, y1).
MINIMIZAR = (710, 5, 728, 19)
CERRAR = (732, 5, 750, 19)
RANURAS = [(214, 178, 546, 210), (214, 218, 546, 250)]
BOTON = (262, 264, 498, 308)
BOTON_ZONA = (222, 244, 538, 328)  # el sprite del botón, con el brillo y las flechas
PROGRESO = (214, 328, 512, 338)
SEGMENTOS = 40
REGISTRO = (214, 343, 560, 385)
SCROLLER = (0, 388, W, 412)
MUSICA = (478, 424, 562, 446)
LEEME = (570, 424, 654, 446)
SALIR = (662, 424, 746, 446)

# Las dos casillas de arriba: en la edición de la traducción va primero la traducción; en la de la
# Definitive Edition, al revés. El engranaje abre la configuración de la Definitive Edition.
MODULOS = {"es": {"traduccion": (214, 146, 372, 168), "de": (380, 146, 546, 168)},
           "de": {"de": (214, 146, 380, 168), "traduccion": (388, 146, 546, 168)}}
IDIOMAS = [(612, 4, 653, 20), (656, 4, 697, 20)]  # español (Argentina) e inglés (Estados Unidos)
MARGEN = 6  # los textos sueltos se guardan con este margen alrededor
FRASE_Y = 125
FRASE_DE, FRASE_ES = "JENSEITS VON GUT UND BÖSE", "MÁS ALLÁ DEL BIEN Y DEL MAL"
RESTABLECER = (558, 356, 642, 378)
LISTO = (650, 356, 734, 378)

_TRAMPA = ("XENOSAGA ES UNA MARCA DE BANDAI NAMCO ENTERTAINMENT, DESARROLLADO POR MONOLITH SOFT",
           "XENOSAGA IS A TRADEMARK OF BANDAI NAMCO ENTERTAINMENT, DEVELOPED BY MONOLITH SOFT")
_MUSICA = ("MÚSICA: «THE IMAGE THEME OF XENOSAGA II», DE YUKI KAJIURA", "MUSIC: “THE IMAGE THEME OF XENOSAGA II” BY YUKI KAJIURA")
CREDITOS = {
    ("es", "es"): ["XENOSAGA EPISODE II EN ESPAÑOL", "TRADUCCIÓN, REVISIÓN Y HERRAMIENTAS: BATNOSKA",
                   "CON LA AYUDA DE CLAUDE (ANTHROPIC)", "DEFINITIVE EDITION: DATOS DE COMBATE INVESTIGADOS POR THESPARDA",
                   _MUSICA[0], _TRAMPA[0], "PROYECTO DE FANS, SIN FINES DE LUCRO",
                   "ERRORES: GITHUB.COM/BATNOSKA/XENOSAGA2-ES O DISCORD @ARGOLLA", "SALUDOS A TODA LA COMUNIDAD XENO"],
    ("es", "en"): ["XENOSAGA EPISODE II IN SPANISH", "TRANSLATION, EDITING AND TOOLS: BATNOSKA",
                   "WITH HELP FROM CLAUDE (ANTHROPIC)", "DEFINITIVE EDITION: BATTLE DATA RESEARCH BY THESPARDA",
                   _MUSICA[1], _TRAMPA[1], "FAN PROJECT, NON-PROFIT",
                   "BUGS: GITHUB.COM/BATNOSKA/XENOSAGA2-ES OR DISCORD @ARGOLLA", "GREETINGS TO THE WHOLE XENO COMMUNITY"],
    ("de", "es"): ["XENOSAGA EPISODE II DEFINITIVE EDITION", "PARCHE: BATNOSKA, CON LA AYUDA DE CLAUDE (ANTHROPIC)",
                   "DATOS DE COMBATE INVESTIGADOS POR THESPARDA", "TRADUCCIÓN AL ESPAÑOL: BATNOSKA",
                   _MUSICA[0], _TRAMPA[0], "PROYECTO DE FANS, SIN FINES DE LUCRO",
                   "ERRORES: GITHUB.COM/BATNOSKA/XENOSAGA2-DEFINITIVE O DISCORD @ARGOLLA", "SALUDOS A TODA LA COMUNIDAD XENO"],
    ("de", "en"): ["XENOSAGA EPISODE II DEFINITIVE EDITION", "PATCH: BATNOSKA, WITH HELP FROM CLAUDE (ANTHROPIC)",
                   "BATTLE DATA RESEARCH: THESPARDA", "SPANISH TRANSLATION: BATNOSKA",
                   _MUSICA[1], _TRAMPA[1], "FAN PROJECT, NON-PROFIT",
                   "BUGS: GITHUB.COM/BATNOSKA/XENOSAGA2-DEFINITIVE OR DISCORD @ARGOLLA", "GREETINGS TO THE WHOLE XENO COMMUNITY"],
}

# Textos que van dibujados en imágenes, por idioma.
ROTULOS = {
    "es": {"boton": "APLICAR PARCHE", "musica": "MÚSICA", "leeme": "LEEME", "salir": "SALIR", "si": "SÍ", "no": "NO",
           "restablecer": "RESTABLECER", "listo": "LISTO", "disco": "DISCO", "sistema": "SISTEMA DE PARCHE",
           "pie": "T.C. 4767 // U.M.N. EN LÍNEA", "traduccion": "TRADUCCIÓN AL ESPAÑOL"},
    "en": {"boton": "APPLY PATCH", "musica": "MUSIC", "leeme": "README", "salir": "EXIT", "si": "YES", "no": "NO",
           "restablecer": "RESET", "listo": "DONE", "disco": "DISC", "sistema": "PATCH SYSTEM",
           "pie": "T.C. 4767 // U.M.N. ONLINE", "traduccion": "SPANISH TRANSLATION"},
}


# ---------------------------------------------------------------- ayudas de dibujo
def font(name, size, variation=None):
    f = ImageFont.truetype(os.path.join(FONTS, name), int(size * S))
    if variation:
        f.set_variation_by_name(variation)
    return f


def px(*v):
    return [int(round(x * S)) for x in v]


def gradient(w, h, stops, vertical=True):
    """Degradé RGBA; stops = [(posición 0..1, (r, g, b, a))]."""
    t = np.linspace(0, 1, h if vertical else w)
    line = np.stack([np.interp(t, [p for p, _ in stops], [c[i] for _, c in stops]) for i in range(4)], axis=1)
    line = line.astype(np.uint8)
    arr = np.repeat(line[:, None, :], w, axis=1) if vertical else np.repeat(line[None, :, :], h, axis=0)
    return Image.fromarray(arr, "RGBA")


def glow(layer, radius, strength=1.0):
    g = layer.filter(ImageFilter.GaussianBlur(radius * S))
    if strength != 1.0:
        a = np.array(g)
        a[..., 3] = np.clip(a[..., 3].astype(np.float32) * strength, 0, 255).astype(np.uint8)
        g = Image.fromarray(a, "RGBA")
    return g


def with_alpha(img, factor):
    a = np.array(img)
    a[..., 3] = (a[..., 3].astype(np.float32) * factor).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def text_layer(size, xy, text, fnt, fill, spacing=0.0):
    """Texto en una capa transparente del tamaño dado, con espaciado entre letras (en px de la ventana)."""
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=255)
        x += fnt.getlength(ch) + spacing * S
    layer = Image.new("RGBA", size, fill)
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    return layer


def text_width(text, fnt, spacing=0.0):
    return sum(fnt.getlength(ch) for ch in text) / S + spacing * len(text)


def glowing_text(img, xy, text, fnt, color, glow_color, spacing=0.0, radius=4, strength=1.8):
    img.alpha_composite(glow(text_layer(img.size, xy, text, fnt, glow_color + (255,), spacing), radius, strength))
    img.alpha_composite(text_layer(img.size, xy, text, fnt, color + (255,), spacing))


def down(img):
    """Del dibujo (S veces el diseño) al tamaño real (E veces el diseño)."""
    return img.resize((round(img.width * E / S), round(img.height * E / S)), Image.LANCZOS)


def fit(img, height):
    return img.resize((int(img.width * height / img.height), int(height)), Image.LANCZOS)


# ---------------------------------------------------------------- arte externo
def descargar():
    """Las imágenes del juego: las baja la primera vez y comprueba que sean las esperadas."""
    carpeta = os.path.join(EXTERNO, "descarga")
    os.makedirs(carpeta, exist_ok=True)
    rutas = {}
    for clave, (url, sha1) in FUENTES.items():
        ruta = os.path.join(carpeta, url.rsplit("/", 1)[1])
        if not os.path.exists(ruta):
            print(f"descargando {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "xenosaga2-es/kit"})
            with urllib.request.urlopen(req, timeout=60) as r, open(ruta, "wb") as f:
                f.write(r.read())
        with open(ruta, "rb") as f:
            if hashlib.sha1(f.read()).hexdigest() != sha1:
                raise SystemExit(f"{ruta} no es el archivo esperado: bórralo para que se descargue de nuevo")
        rutas[clave] = ruta
    return rutas


def sin_fondo_blanco(path):
    """Saca el fondo blanco de un render: el blanco unido al borde pasa a transparente."""
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    dist = 255 - rgb.min(axis=2)  # cuánto se aparta cada píxel del blanco
    mask = Image.fromarray(np.where(dist < 14, 255, 0).astype(np.uint8)).copy()  # copia: la de numpy es de solo lectura
    h, w = dist.shape
    for xy in [(x, y) for x in range(0, w, 25) for y in (0, h - 1)] + [(x, y) for y in range(0, h, 25) for x in (0, w - 1)]:
        if mask.getpixel(xy) == 255:
            ImageDraw.floodfill(mask, xy, 128)
    background = np.asarray(mask) == 128
    grown = np.asarray(Image.fromarray(background.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0
    alpha = np.where(~grown, 1.0, np.where(background, 0.0, np.clip(dist / 60, 0, 1)))
    alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))) / 255
    alpha[background & (dist < 6)] = 0
    return _unmix_white(rgb, alpha)


def _unmix_white(rgb, alpha):
    """Quita el blanco mezclado en los bordes semitransparentes."""
    a = np.clip(alpha, 1e-3, 1)[..., None]
    color = np.clip((rgb - 255 * (1 - a)) / a, 0, 255)
    img = Image.fromarray(np.dstack([color, alpha[..., None] * 255]).astype(np.uint8), "RGBA")
    return img.crop(img.getchannel("A").getbbox())


def solo_figura(img):
    """Deja la figura principal y saca marcas de agua sueltas."""
    a = img.getchannel("A")
    small = a.resize((a.width // 8, a.height // 8)).point(lambda v: 255 if v > 40 else 0).copy()
    ys, xs = np.nonzero(np.asarray(small))
    k = np.argmin((ys - small.height // 2) ** 2 + (xs - small.width // 2) ** 2)
    ImageDraw.floodfill(small, (int(xs[k]), int(ys[k])), 128)
    keep = small.point(lambda v: 255 if v == 128 else 0).filter(ImageFilter.MaxFilter(5)).resize(a.size)
    img.putalpha(ImageChops.multiply(a, keep))
    return img.crop(img.getchannel("A").getbbox())


def logo_sin_fondo(path):
    """El logo viene sobre blanco: el blanco pasa a transparente y el subtítulo, que es negro, a plateado."""
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    lg = _unmix_white(rgb, np.clip((255 - rgb.min(axis=2)) / 255 * 1.6, 0, 1))
    arr = np.array(lg)
    c = arr[..., :3].astype(np.int32)
    gray = (c.max(axis=2) - c.min(axis=2)) < 40
    gray[: int(lg.height * 0.86)] = False  # el "II", que es violeta, queda más arriba
    arr[gray, :3] = (226, 230, 244)
    lg = Image.fromarray(arr, "RGBA")
    box = lg.getchannel("A").filter(ImageFilter.MinFilter(9)).getbbox()
    return lg.crop((max(box[0] - 20, 0), max(box[1] - 20, 0), box[2] + 20, box[3] + 20))


def tono(img, tint, amount, fade_from_left):
    """Tono a dos colores como los pósteres del juego, desvanecido hacia el centro y hacia abajo."""
    arr = np.asarray(img).astype(np.float32)
    lum = (arr[..., :3] @ np.array([0.3, 0.59, 0.11]))[..., None] / 255
    arr[..., :3] = arr[..., :3] * (1 - amount) + lum * np.array(tint, dtype=np.float32) * amount
    x = np.linspace(0, 1, img.width)
    ramp = np.clip((1 - x) / 0.55, 0, 1) if fade_from_left else np.clip(x / 0.55, 0, 1)
    ramp = 0.25 + 0.75 * ramp ** 0.8
    vramp = np.clip((1 - np.linspace(0, 1, img.height)) / 0.25, 0, 1)
    arr[..., 3] *= ramp[None, :] * vramp[:, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


# ---------------------------------------------------------------- fondo
def fondo_base():
    rnd = random.Random(7)
    w, h = W * S, H * S
    bg = gradient(w, h, [(0, (6, 8, 20, 255)), (0.55, (10, 12, 36, 255)), (1, (4, 5, 14, 255))])
    # franjas teñidas, como el póster del grupo
    tints = [(70, 190, 110), (110, 200, 210), (225, 228, 240), (165, 130, 235), (125, 70, 210), (95, 95, 230), (70, 120, 240)]
    sw = w / len(tints)
    for i, col in enumerate(tints):
        strip = gradient(int(sw) + 1, h, [(0, col + (52,)), (0.45, col + (22,)), (0.8, col + (6,)), (1, col + (0,))])
        a = np.array(strip)
        noise = (np.random.default_rng(i).random((h, int(sw) + 1)) * 18).astype(np.int32)
        a[..., 3] = np.clip(a[..., 3].astype(np.int32) + noise - 9, 0, 255).astype(np.uint8)
        bg.alpha_composite(Image.fromarray(a, "RGBA"), (int(i * sw), 0))
        ImageDraw.Draw(bg).line([(int(i * sw), 0), (int(i * sw), h)], fill=(0, 0, 0, 120), width=S)
    # vidrio rajado
    cracks = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cracks)
    for _ in range(26):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h * 0.6)
        ang = rnd.uniform(0, math.tau)
        pts = [(x, y)]
        for _ in range(rnd.randint(3, 7)):
            ang += rnd.uniform(-0.7, 0.7)
            x += math.cos(ang) * rnd.uniform(20, 70) * S
            y += math.sin(ang) * rnd.uniform(20, 70) * S
            pts.append((x, y))
        cd.line(pts, fill=(255, 255, 255, rnd.randint(18, 45)), width=1)
    bg.alpha_composite(cracks)
    # haz diagonal de luz
    beam = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(beam).polygon(px(250, 0, 330, 0, 140, H, 60, H), fill=(255, 255, 255, 14))
    bg.alpha_composite(beam.filter(ImageFilter.GaussianBlur(4 * S)))
    # piso de grilla en perspectiva
    grid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    horizon, vx = 300 * S, W / 2 * S
    for i in range(1, 14):
        y = horizon + (i ** 1.9) * 1.1 * S
        if y < h:
            gd.line([(0, y), (w, y)], fill=(80, 200, 255, 60), width=1)
    for i in range(-18, 19):
        gd.line([(vx, horizon), (vx + i * 70 * S, h + 200 * S)], fill=(80, 200, 255, 50), width=1)
    fade = gradient(w, h, [(0, (0, 0, 0, 0)), (0.7, (0, 0, 0, 0)), (1, (0, 0, 0, 255))])
    grid.putalpha(ImageChops.multiply(grid.getchannel("A"), fade.getchannel("A")))
    bg.alpha_composite(grid)
    return bg


def lineas_y_vineta():
    """Factor por píxel: líneas de escaneo y viñeta. Se aplica igual a las dos capas del fondo."""
    h, w = H * S, W * S
    f = np.ones((h, w), np.float32)
    f[::2 * S] *= 0.78
    f[1::2 * S] *= 0.78
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    return f * np.clip(1.15 - 0.35 * r ** 2, 0.55, 1)


def aplicar_factor(img, factor):
    a = np.asarray(img).astype(np.float32)
    a[..., :3] *= factor[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def chamfer(box, cut):
    x0, y0, x1, y1 = px(*box)
    c = cut * S
    return [(x0, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1), (x0 + c, y1), (x0, y1 - c)]


def capas(img_ext):
    """Fondo de atrás (opaco: base y Zohar) y de adelante (transparente: personajes, logo e interfaz fija).
    Entre las dos va el brillo de la gema, que late. Los textos que dependen del idioma no van acá:
    son imágenes aparte (textos())."""
    atras = fondo_base()
    size = atras.size

    zohar = fit(img_ext["zohar"], 400 * S)
    zx, zy = (W * S - zohar.width) // 2, 44 * S
    gema = (zx + zohar.width * 0.5, zy + zohar.height * 0.165)
    rays = Image.new("RGBA", size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    for i in range(18):
        a = i / 18 * math.tau + 0.12
        rd.polygon([gema, (gema[0] + math.cos(a - 0.045) * 420 * S, gema[1] + math.sin(a - 0.045) * 420 * S),
                    (gema[0] + math.cos(a + 0.045) * 420 * S, gema[1] + math.sin(a + 0.045) * 420 * S)], fill=(110, 230, 255, 26))
    atras.alpha_composite(glow(rays, 8))
    zl = Image.new("RGBA", size, (0, 0, 0, 0))
    zl.alpha_composite(zohar, (zx, zy))
    warm = Image.new("RGBA", size, (255, 196, 100, 255))
    warm.putalpha(zl.getchannel("A"))
    atras.alpha_composite(glow(warm, 10, 0.55))
    atras.alpha_composite(with_alpha(zl, 0.55))

    frente = Image.new("RGBA", size, (0, 0, 0, 0))
    jr = tono(fit(img_ext["jr"].transpose(Image.FLIP_LEFT_RIGHT), 450 * S), (255, 120, 95), 0.28, False)
    al = tono(fit(img_ext["albedo"], 452 * S), (175, 150, 255), 0.32, True)
    for fig, (x, y), rim in ((jr, (-58 * S, 30 * S), (255, 90, 70)), (al, (W * S - al.width + 74 * S, 28 * S), (160, 120, 255))):
        r = Image.new("RGBA", size, rim + (255,))
        m = Image.new("L", size, 0)
        m.paste(fig.getchannel("A"), (x, y))
        r.putalpha(m)
        frente.alpha_composite(glow(r, 7, 0.9))
        frente.alpha_composite(fig, (x, y))

    shade = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(shade).rounded_rectangle(px(200, 172, 560, 386), radius=30 * S, fill=(3, 5, 16, 190))
    frente.alpha_composite(shade.filter(ImageFilter.GaussianBlur(18 * S)))

    # sin el subtítulo alemán, que el aplicador dibuja aparte (y traduce): ver frase()
    lg = img_ext["logo"]
    sin_sub = lg.crop((0, 0, lg.width, int(lg.height * 0.905)))
    lg = fit(sin_sub, 104 * S * sin_sub.height / lg.height)
    ll = Image.new("RGBA", size, (0, 0, 0, 0))
    ll.alpha_composite(lg, ((W * S - lg.width) // 2, 27 * S))
    halo = Image.new("RGBA", size, (200, 215, 255, 255))
    halo.putalpha(ll.getchannel("A").filter(ImageFilter.MaxFilter(7)))
    frente.alpha_composite(glow(halo, 5, 1.7))
    frente.alpha_composite(ll)
    d = ImageDraw.Draw(frente)

    # barra de título
    d.rectangle(px(0, 0, W, 24), fill=(4, 6, 16, 215))
    d.line(px(0, 24, W, 24), fill=CYAN + (120,), width=S)

    # ranuras vacías (el estado lo dibuja el aplicador encima)
    for i, box in enumerate(RANURAS):
        x0, y0, x1, y1 = box
        d.polygon(chamfer(box, 9), fill=(8, 12, 34, 215))
        d.line(chamfer(box, 9) + [chamfer(box, 9)[0]], fill=CYAN + (70,), width=S)
        d.rectangle(px(x0, y0, x0 + 4, y1), fill=(90, 100, 130, 255))
        d.text(px(x0 + 12, y0 + 18), ("SLUS-20892", "SLUS-21133")[i], font=font("consola.ttf", 9), fill=CYAN + (170,))

    # banda del scroller y pie
    x0, y0, x1, y1 = SCROLLER
    d.rectangle(px(x0, y0, x1, y1), fill=(2, 4, 12, 225))
    d.line(px(x0, y0, x1, y0), fill=VIOLET + (150,), width=S)
    d.line(px(x0, y1, x1, y1), fill=VIOLET + (150,), width=S)
    d.rectangle(px(0, y1 + 1, W, H), fill=(4, 6, 16, 235))
    rnd = random.Random(4)
    cx = 14
    while cx < 78:
        bw = rnd.choice([1, 1, 2, 3])
        if rnd.random() > 0.35:
            d.rectangle(px(cx, 424, cx + bw * 0.6, 446), fill=(170, 190, 220, 160))
        cx += bw * 0.9
    d.text(px(86, 436), "NTSC-U · SLUS-20892 · SLUS-21133", font=font("consola.ttf", 9), fill=(110, 125, 165, 220))

    # marco cromado y esquinas de HUD
    d.rectangle(px(0, 0, W - 0.5, H - 0.5), outline=(200, 210, 230, 255), width=S)
    d.rectangle(px(1.5, 1.5, W - 2, H - 2), outline=(60, 66, 90, 255), width=S)
    for cx, cy, sx, sy in ((6, 30, 1, 1), (W - 6, 30, -1, 1), (6, H - 6, 1, -1), (W - 6, H - 6, -1, -1)):
        d.line(px(cx, cy, cx + 14 * sx, cy), fill=CYAN + (255,), width=2 * S)
        d.line(px(cx, cy, cx, cy + 14 * sy), fill=CYAN + (255,), width=2 * S)

    factor = lineas_y_vineta()
    gx, gy = gema[0] / S, gema[1] / S
    return down(aplicar_factor(atras, factor)), down(aplicar_factor(frente, factor)), (int(gx), int(gy))


def brillo_gema():
    w, h = 140, 170
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse(px(w / 2 - 26, h / 2 - 34, w / 2 + 26, h / 2 + 34), fill=(90, 255, 230, 230))
    return down(glow(img, 16, 1.6))


# ---------------------------------------------------------------- botones
def boton_principal(estado, label):
    """El botón de aplicar: rombo alargado de cristal con borde cromado y flechas de HUD."""
    zx0, zy0, zx1, zy1 = BOTON_ZONA
    img = Image.new("RGBA", ((zx1 - zx0) * S, (zy1 - zy0) * S), (0, 0, 0, 0))
    x0, y0, x1, y1 = px(BOTON[0] - zx0, BOTON[1] - zy0, BOTON[2] - zx0, BOTON[3] - zy0)
    w, h = x1 - x0, y1 - y0
    tip = h // 2
    off = S if estado == "presionado" else 0
    shape = [(x0 + tip, y0), (x1 - tip, y0), (x1, y0 + h // 2), (x1 - tip, y1), (x0 + tip, y1), (x0, y0 + h // 2)]
    inner = [(x0 + tip + 2 * S, y0 + 3 * S), (x1 - tip - 2 * S, y0 + 3 * S), (x1 - 4 * S, y0 + h // 2),
             (x1 - tip - 2 * S, y1 - 3 * S), (x0 + tip + 2 * S, y1 - 3 * S), (x0 + 4 * S, y0 + h // 2)]
    activo = estado != "inactivo"
    if activo:
        halo = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(halo).polygon(shape, fill=CYAN + (255 if estado == "hover" else 200,))
        img.alpha_composite(glow(halo, 12, 1.6 if estado == "hover" else 1.2))
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).polygon(shape, fill=255)
    mi = Image.new("L", img.size, 0)
    ImageDraw.Draw(mi).polygon(inner, fill=255)
    stops = {"normal": [(0, (40, 70, 150, 255)), (0.48, (10, 22, 70, 255)), (0.52, (6, 14, 48, 255)), (1, (40, 170, 230, 255))],
             "hover": [(0, (70, 110, 200, 255)), (0.48, (20, 40, 110, 255)), (0.52, (10, 26, 80, 255)), (1, (80, 210, 255, 255))],
             "presionado": [(0, (10, 30, 80, 255)), (0.5, (6, 14, 48, 255)), (1, (30, 120, 190, 255))],
             "inactivo": [(0, (40, 44, 60, 255)), (0.5, (16, 18, 28, 255)), (1, (40, 46, 66, 255))]}[estado]
    glass = Image.new("RGBA", img.size, (0, 0, 0, 0))
    glass.paste(gradient(w, h, stops), (x0, y0), mi.crop((x0, y0, x1, y1)))
    img.alpha_composite(glass)
    shine = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shine).polygon([(x0 + tip + 4 * S, y0 + 5 * S), (x1 - tip - 4 * S, y0 + 5 * S),
                                   (x1 - tip - 14 * S, y0 + h * 0.42), (x0 + tip + 14 * S, y0 + h * 0.42)],
                                  fill=(255, 255, 255, 70 if activo else 25))
    shine.putalpha(ImageChops.multiply(shine.getchannel("A"), mi))
    img.alpha_composite(shine)
    chrome = gradient(img.width, img.height, [(0, (250, 252, 255, 255)), (0.5, (120, 130, 160, 255)), (1, (230, 236, 250, 255))]
                      if activo else [(0, (150, 154, 168, 255)), (1, (90, 94, 110, 255))])
    ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ring.paste(chrome, (0, 0), ImageChops.subtract(m, mi))
    img.alpha_composite(ring)
    lf = font("bahnschrift.ttf", 17, "Bold SemiCondensed")
    tx = x0 / S + (w / S - text_width(label, lf, 2.2)) / 2
    color = (255, 255, 255) if activo else (130, 136, 156)
    if activo:
        glowing_text(img, (tx * S + off, y0 + h * 0.16 + off), label, lf, color, CYAN, 2.2, 4, 2)
    else:
        img.alpha_composite(text_layer(img.size, (tx * S, y0 + h * 0.16), label, lf, color + (255,), 2.2))
    d = ImageDraw.Draw(img)
    for side in (-1, 1):
        cx = (x0 - 10 * S) if side < 0 else (x1 + 10 * S)
        cy = y0 + h // 2
        for k in range(3):
            o = k * 7 * S * side
            col = (CYAN if activo else (90, 96, 116)) + (230 - k * 70,)
            d.polygon([(cx + o, cy - 5 * S), (cx + o - 5 * S * side, cy), (cx + o, cy + 5 * S)], fill=col)
    return down(img)


def boton_chico(label, estado, size=(84, 22)):
    """Botón cromado de los de abajo (y de los diálogos)."""
    w, h = size[0] * S, size[1] * S
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    stops = {"normal": [(0, (225, 230, 240, 255)), (0.48, (140, 148, 168, 255)), (0.52, (60, 66, 84, 255)), (1, (150, 158, 180, 255))],
             "hover": [(0, (240, 250, 255, 255)), (0.48, (160, 200, 230, 255)), (0.52, (50, 90, 140, 255)), (1, (120, 210, 255, 255))],
             "presionado": [(0, (60, 66, 84, 255)), (0.5, (110, 118, 140, 255)), (1, (200, 206, 220, 255))]}[estado]
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=3 * S, fill=255)
    img.paste(gradient(w, h, stops), (0, 0), m)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=3 * S, outline=(20, 24, 36, 255), width=S)
    bf = font("bahnschrift.ttf", 11, "Bold SemiCondensed")
    off = S if estado == "presionado" else 0
    tw = bf.getlength(label)
    x = (w - tw) / 2 if label not in ("MÚSICA", "MUSIC") else 9 * S  # a la derecha van las barritas del volumen
    d.text((x + off, (h - bf.size * 1.18) / 2 + off), label, font=bf, fill=(14, 16, 26, 255))
    return down(img)


def boton_titulo(glyph, estado):
    return boton_chico(glyph, estado, (18, 14))


CHIPS = {  # estado: (español, inglés, color)
    "original": ("ORIGINAL ✓", "ORIGINAL ✓", (20, 140, 120)),
    "traducida": ("YA TRADUCIDA", "TRANSLATED", (96, 70, 190)),
    "distinta": ("OTRA VERSIÓN", "OTHER VERSION", (190, 120, 20)),
    "anterior": ("VERSIÓN VIEJA", "OLD VERSION", (200, 90, 40)),
    "novalida": ("NO VÁLIDA", "INVALID", (180, 40, 50)),
    "encurso": ("EN CURSO", "WORKING", (30, 120, 190)),
    "lista": ("LISTA ✓", "DONE ✓", (30, 170, 110)),
    "error": ("ERROR", "ERROR", (180, 40, 50)),
}


def chip(texto, color):
    w, h = 68 * S, 16 * S
    img = Image.new("RGBA", (w, h), color + (255,))
    d = ImageDraw.Draw(img)
    cf = font("bahnschrift.ttf", 10, "Bold SemiCondensed")
    sym = ImageFont.truetype(os.path.join(FONTS, "seguisym.ttf"), int(10 * S))
    parts = [(p, sym if p == "✓" else cf) for p in texto.replace(" ✓", " |✓").split("|")]
    tw = sum(f.getlength(p) for p, f in parts)
    x = (w - tw) / 2
    for p, f in parts:
        d.text((x, (h - cf.size * 1.2) / 2), p, font=f, fill=(235, 255, 250, 255))
        x += f.getlength(p)
    return down(img)


def scroller(partes):
    """La tira de créditos con brillo; el aplicador la dibuja en rebanadas que ondulan."""
    texto = "".join(f"★ {p} " for p in partes)
    lf = ImageFont.truetype(os.path.join(FONTS, "lucon.ttf"), 12 * S)
    star = ImageFont.truetype(os.path.join(FONTS, "seguisym.ttf"), 11 * S)
    width = int(sum((star if ch == "★" else lf).getlength(ch) for ch in texto)) + 4 * S
    h = 22 * S
    layer = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x = 0
    for i, ch in enumerate(texto):
        t = (math.sin(i * 0.2) + 1) / 2
        col = tuple(int(CYAN[c] * (1 - t) + 255 * t) for c in range(3)) + (255,)
        f = star if ch == "★" else lf
        d.text((x, 3 * S), ch, font=f, fill=(255, 210, 120, 255) if ch == "★" else col)
        x += f.getlength(ch)
    out = glow(layer, 3, 1.2)
    out.alpha_composite(layer)
    return down(out)


# ---------------------------------------------------------------- textos sueltos, banderas y la frase
def suelto(texto, fnt, color, spacing=0.0, brillo=None):
    """Un texto en una imagen justa, con MARGEN alrededor: el aplicador la dibuja en
    (x - MARGEN, y - MARGEN) para que el texto empiece en (x, y)."""
    w = text_width(texto, fnt, spacing) + 2 * MARGEN
    h = fnt.size / S * 1.4 + 2 * MARGEN
    img = Image.new("RGBA", (int(w * S), int(h * S)), (0, 0, 0, 0))
    xy = (MARGEN * S, MARGEN * S)
    if brillo:
        img.alpha_composite(glow(text_layer(img.size, xy, texto, fnt, brillo + (255,), spacing), 3, 1.2))
    img.alpha_composite(text_layer(img.size, xy, texto, fnt, color, spacing))
    return down(img)


def textos(edicion, version, idioma):
    """Los textos de la ventana que cambian con el idioma (y el título, con la edición)."""
    rot = ROTULOS[idioma]
    sigla = "XS2·ES" if edicion == "es" else "XS2·DE"
    negrita = font("bahnschrift.ttf", 12, "Bold SemiCondensed")
    modulo = font("bahnschrift.ttf", 11.5, "Bold SemiCondensed")
    out = {
        f"titulo_{idioma}": suelto(f"{sigla}  //  {rot['sistema']}  //  v{version}", font("consola.ttf", 10.5), CYAN + (230,)),
        f"pie_{idioma}": suelto(rot["pie"], font("consola.ttf", 9), (150, 170, 210, 220)),
        f"mod_traduccion_{idioma}_on": suelto(rot["traduccion"], modulo, (240, 248, 255, 255), 0.6, CYAN),
        f"mod_traduccion_{idioma}_off": suelto(rot["traduccion"], modulo, (130, 142, 170, 255), 0.6),
    }
    for i in (1, 2):
        out[f"disco{i}_{idioma}"] = suelto(f"{rot['disco']} {i}", negrita, (240, 245, 255, 255))
    chica = font("bahnschrift.ttf", 9.5, "Bold SemiCondensed")
    sigla_idioma = idioma.upper()
    out[f"idioma_{idioma}_on"] = suelto(sigla_idioma, chica, (255, 255, 255, 255))
    out[f"idioma_{idioma}_off"] = suelto(sigla_idioma, chica, (120, 132, 165, 255))
    return out


def comunes():
    """Lo que no cambia con el idioma: la casilla de la Definitive Edition y el engranaje."""
    modulo = font("bahnschrift.ttf", 11.5, "Bold SemiCondensed")
    sym = ImageFont.truetype(os.path.join(FONTS, "seguisym.ttf"), int(11 * S))
    return {
        "mod_de_on": suelto("DEFINITIVE EDITION", modulo, (240, 248, 255, 255), 0.6, CYAN),
        "mod_de_off": suelto("DEFINITIVE EDITION", modulo, (130, 142, 170, 255), 0.6),
        "engranaje": suelto("⚙", sym, (230, 250, 255, 255)),
    }


def bandera(pais, activo, ancho=15, alto=10):
    """Bandera dibujada a 8x, achicada y pasada por el filtro de la ventana: mezcla con un tono a dos
    colores (azul noche a cian claro), líneas de barrido y un reflejo arriba."""
    k = 8
    w, h = ancho * k, alto * k
    f = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(f)
    if pais == "ar":
        celeste, sol = (116, 172, 223), (246, 180, 14)
        d.rectangle((0, 0, w, h / 3), fill=celeste)
        d.rectangle((0, 2 * h / 3, w, h), fill=celeste)
        cx, cy, r = w / 2, h / 2, h / 9
        for i in range(16):  # el Sol de Mayo
            a = i / 16 * math.tau
            d.line((cx, cy, cx + math.cos(a) * r * 1.9, cy + math.sin(a) * r * 1.9), fill=sol, width=k // 2)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=sol)
    else:
        franja = h / 13
        for i in range(0, 13, 2):
            d.rectangle((0, i * franja, w, (i + 1) * franja), fill=(178, 34, 52))
        cw, ch = w * 0.4, franja * 7
        d.rectangle((0, 0, cw, ch), fill=(60, 59, 110))
        for fila in range(5):
            for col in range(6 - fila % 2):
                x, y = cw * (col + 0.5 + (fila % 2) * 0.5) / 6, ch * (fila + 0.5) / 5
                d.ellipse((x - k * 0.7, y - k * 0.7, x + k * 0.7, y + k * 0.7), fill=(255, 255, 255))
    a = np.asarray(f.resize((round(ancho * E), round(alto * E)), Image.LANCZOS)).astype(np.float32) / 255
    lum = (a @ np.array([0.3, 0.59, 0.11]))[..., None]
    oscuro, claro = np.array([10, 20, 60]) / 255, np.array([190, 240, 255]) / 255
    duo = oscuro + (claro - oscuro) * lum
    mezcla = a * 0.5 + duo * 0.5 if activo else (a * 0.2 + duo * 0.8) * 0.55
    mezcla[::2] *= 0.86
    mezcla[: mezcla.shape[0] // 2] += 0.08
    img = Image.fromarray((np.clip(mezcla, 0, 1) * 255).astype(np.uint8), "RGB").convert("RGBA")
    ImageDraw.Draw(img).rectangle((0, 0, img.width - 1, img.height - 1), outline=CYAN + ((200,) if activo else (60,)))
    return img


def frase():
    """El subtítulo bajo el logo ("Jenseits von Gut und Böse", que el aplicador va traduciendo
    mientras aplica la traducción). Imágenes del ancho de la ventana para dibujar en
    (0, FRASE_Y - MARGEN): en alemán, en español, un halo suave del español (letra por letra,
    mientras se descifra) y el brillo final, con un destello horizontal y remates a los costados.
    Devuelve también dónde empieza y cuánto mide cada letra del español."""
    gf = font("GARA.TTF", 11.5)
    esp = 3.2
    alto = 30

    def capa(texto, color):
        ancho = sum(gf.getlength(c) / S + esp for c in texto) - esp
        x0 = (W - ancho) / 2
        img = Image.new("RGBA", (W * S, alto * S), (0, 0, 0, 0))
        return img, x0, text_layer(img.size, (x0 * S, MARGEN * S), texto, gf, color, esp)

    out = {}
    _, _, de = capa(FRASE_DE, (190, 198, 222, 230))
    out["frase_de"] = down(de)
    img, x0, es = capa(FRASE_ES, (255, 255, 255, 255))
    out["frase_es"] = down(es)
    _, _, cian = capa(FRASE_ES, CYAN + (255,))
    out["frase_es_halo"] = down(glow(cian, 4, 1.3))
    ancho = sum(gf.getlength(c) / S + esp for c in FRASE_ES) - esp
    brillo = Image.new("RGBA", img.size, (0, 0, 0, 0))
    xs = np.linspace(-1, 1, img.width)
    alfa = (np.clip(1 - np.abs(xs) * 1.15, 0, 1) ** 2.2 * 255).astype(np.uint8)
    franja = Image.fromarray(np.tile(alfa, (2 * S, 1)), "L")
    rayo = Image.new("RGBA", img.size, (0, 0, 0, 0))
    rayo.paste(Image.new("RGBA", franja.size, (200, 250, 255, 255)), (0, (MARGEN + 8) * S), franja)
    brillo.alpha_composite(glow(rayo, 5, 2.5))
    brillo.alpha_composite(rayo)
    grueso = cian.filter(ImageFilter.MaxFilter(7))
    brillo.alpha_composite(glow(grueso, 12, 2.2))
    brillo.alpha_composite(glow(grueso, 4, 1.6))
    d = ImageDraw.Draw(brillo)
    y = MARGEN + 8
    for lado in (-1, 1):
        xa = x0 - 10 if lado < 0 else x0 + ancho + 10
        xb = xa + 30 * lado
        d.line(px(xa, y, xb, y), fill=CYAN + (220,), width=S)
        d.polygon([tuple(px(xb, y - 2.5)), tuple(px(xb + 2.5 * lado, y)), tuple(px(xb, y + 2.5)), tuple(px(xb - 2.5 * lado, y))],
                  fill=(230, 250, 255, 255))
    out["frase_es_brillo"] = down(brillo)
    xs_letras, anchos, x = [], [], x0
    for c in FRASE_ES:
        xs_letras.append(round(x, 2))
        anchos.append(round(gf.getlength(c) / S, 2))
        x += gf.getlength(c) / S + esp
    return out, xs_letras, anchos


# ---------------------------------------------------------------- sonidos
def wav(samples, rate=22050):
    data = np.clip(samples, -1, 1)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((data * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def sonidos(rate=22050):
    def t(sec):
        return np.arange(int(sec * rate)) / rate

    def tone(freqs, sec, shape="sine"):
        tt = t(sec)
        f = np.interp(tt, np.linspace(0, sec, len(freqs)), freqs)
        phase = 2 * np.pi * np.cumsum(f) / rate
        if shape == "square":
            return np.sign(np.sin(phase)) * 0.6
        if shape == "tri":
            return 2 / np.pi * np.arcsin(np.sin(phase))
        return np.sin(phase)

    def env(n, attack=0.005, decay=4.0):
        tt = np.arange(n) / rate
        return np.minimum(tt / attack, 1) * np.exp(-tt * decay)

    hover = tone([1800, 2600], 0.06) * env(int(0.06 * rate), 0.002, 40) * 0.10
    c1 = tone([900, 900], 0.05, "tri") * env(int(0.05 * rate), 0.002, 30)
    c2 = tone([1500, 1500], 0.07, "tri") * env(int(0.07 * rate), 0.002, 25)
    click = np.concatenate([c1, c2]) * 0.16
    start = tone([300, 1700], 0.38, "tri") * env(int(0.38 * rate), 0.01, 5) * 0.16
    start += tone([600, 3400], 0.38) * env(int(0.38 * rate), 0.01, 6) * 0.05
    notes = [1047, 1319, 1568, 2093]
    ok = np.zeros(int(0.9 * rate))
    for k, f in enumerate(notes):
        s = tone([f, f], 0.5, "tri") * env(int(0.5 * rate), 0.004, 6)
        i = int(k * 0.09 * rate)
        ok[i:i + len(s)] += s[: len(ok) - i]
    echo = np.zeros_like(ok)
    lag = int(0.14 * rate)
    echo[lag:] = ok[:-lag] * 0.35
    ok = (ok + echo) * 0.11
    tt = t(0.32)
    error = tone([190, 150], 0.32, "square") * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 18 * tt))) * env(len(tt), 0.005, 6) * 0.10
    return {"sfx_hover.wav": wav(hover), "sfx_click.wav": wav(click), "sfx_inicio.wav": wav(start),
            "sfx_ok.wav": wav(ok), "sfx_error.wav": wav(error)}


# ---------------------------------------------------------------- ícono y medidas
def icono(zohar, path):
    """El ícono: la parte de arriba del Zohar (losa, brazos y gema), centrada en un cuadrado."""
    top = zohar.crop((0, 0, zohar.width, int(zohar.width * 1.05)))
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = []
    for sz in sizes:
        ic = top.resize((int(top.width * sz / top.height), sz), Image.LANCZOS)
        canvas = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        canvas.alpha_composite(ic, ((sz - ic.width) // 2, 0))
        imgs.append(canvas)
    imgs[-1].save(path, format="ICO", sizes=[(s, s) for s in sizes], append_images=imgs[:-1])


def diseno_cs(gema, path, edicion, frase_x, frase_w):
    def rect(b):
        return f"new Rectangle({b[0]}, {b[1]}, {b[2] - b[0]}, {b[3] - b[1]})"

    def floats(v):
        return ", ".join(f"{x}f" for x in v)

    bx0, by0, bx1, by1 = BOTON
    tip = (by1 - by0) // 2
    forma = [(bx0 + tip + 2, by0 + 3), (bx1 - tip - 2, by0 + 3), (bx1 - 4, by0 + tip), (bx1 - tip - 2, by1 - 3),
             (bx0 + tip + 2, by1 - 3), (bx0 + 4, by0 + tip)]
    mod = MODULOS[edicion]
    lines = [
        "// Generado por tools/aplicador/arte.py: medidas de la ventana y del arte. No editar a mano.",
        "// Están en medidas de diseño; la ventana real mide Escala veces más, como las imágenes.",
        "using System.Drawing;",
        "",
        "static class Diseno",
        "{",
        f"    public const float Escala = {E}f;",
        f"    public const int Ancho = {W}, Alto = {H}, Segmentos = {SEGMENTOS}, Margen = {MARGEN};",
        f"    public static readonly Rectangle Minimizar = {rect(MINIMIZAR)}, Cerrar = {rect(CERRAR)};",
        f"    public static readonly Rectangle[] Ranuras = {{ {rect(RANURAS[0])}, {rect(RANURAS[1])} }};",
        f"    public static readonly Rectangle Boton = {rect(BOTON)}, BotonZona = {rect(BOTON_ZONA)};",
        "    public static readonly Point[] BotonForma = { " + ", ".join(f"new Point({x}, {y})" for x, y in forma) + " };",
        f"    public static readonly Rectangle Progreso = {rect(PROGRESO)}, Registro = {rect(REGISTRO)}, Scroller = {rect(SCROLLER)};",
        f"    public static readonly Rectangle Musica = {rect(MUSICA)}, Leeme = {rect(LEEME)}, Salir = {rect(SALIR)};",
        f"    public static readonly Rectangle ModuloTraduccion = {rect(mod['traduccion'])}, ModuloDe = {rect(mod['de'])};",
        f"    public static readonly Rectangle[] Idiomas = {{ {rect(IDIOMAS[0])}, {rect(IDIOMAS[1])} }};",
        f"    public static readonly Rectangle Restablecer = {rect(RESTABLECER)}, Listo = {rect(LISTO)};",
        f"    public static readonly Point Gema = new Point({gema[0]}, {gema[1]});",
        f"    public const float FraseY = {FRASE_Y}f;",
        f'    public const string FraseEs = "{FRASE_ES}";',
        f"    public static readonly float[] FraseX = {{ {floats(frase_x)} }}, FraseAncho = {{ {floats(frase_w)} }};",
        "}",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def generar(version, carpeta, edicion="es", con_de=True):
    """Arma en carpeta: arte.zip (imágenes, sonidos y música), Diseno.cs e icono.ico. edicion es la de
    la traducción ("es") o la de la Definitive Edition ("de"): cambian el título, los créditos y el
    orden de las casillas."""
    os.makedirs(carpeta, exist_ok=True)
    rutas = descargar()
    img_ext = {
        "zohar": Image.open(rutas["zohar"]).convert("RGBA"),
        "jr": solo_figura(sin_fondo_blanco(rutas["jr"])),
        "albedo": solo_figura(sin_fondo_blanco(rutas["albedo"])),
        "logo": logo_sin_fondo(rutas["logo"]),
    }
    img_ext["zohar"] = img_ext["zohar"].crop(img_ext["zohar"].getchannel("A").getbbox())
    atras, frente, gema = capas(img_ext)
    pngs = {"fondo_atras.png": atras, "fondo_frente.png": frente, "gema.png": brillo_gema()}
    for idioma in ("es", "en"):
        rot = ROTULOS[idioma]
        for estado in ("normal", "hover", "presionado", "inactivo"):
            pngs[f"boton_{idioma}_{estado}.png"] = boton_principal(estado, rot["boton"])
        for nombre in ("musica", "leeme", "salir", "si", "no", "restablecer", "listo"):
            for estado in ("normal", "hover", "presionado"):
                pngs[f"{nombre}_{idioma}_{estado}.png"] = boton_chico(rot[nombre], estado)
        for clave, (es, en, color) in CHIPS.items():
            pngs[f"chip_{idioma}_{clave}.png"] = chip(es if idioma == "es" else en, color)
        creditos = [c for c in CREDITOS[(edicion, idioma)] if con_de or "DEFINITIVE EDITION:" not in c]
        pngs[f"scroller_{idioma}.png"] = scroller(creditos)
        pngs.update({k + ".png": v for k, v in textos(edicion, version, idioma).items()})
    for nombre, glyph in (("minimizar", "_"), ("cerrar", "×")):
        for estado in ("normal", "hover", "presionado"):
            pngs[f"{nombre}_{estado}.png"] = boton_titulo(glyph, estado)
    pngs.update({k + ".png": v for k, v in comunes().items()})
    for pais in ("ar", "us"):
        for activo in (True, False):
            pngs[f"bandera_{pais}_{'on' if activo else 'off'}.png"] = bandera(pais, activo)
    imgs_frase, frase_x, frase_w = frase()
    pngs.update({k + ".png": v for k, v in imgs_frase.items()})

    arte = os.path.join(carpeta, "arte.zip")
    with zipfile.ZipFile(arte, "w", zipfile.ZIP_STORED) as z:
        for nombre, img in pngs.items():
            buf = io.BytesIO()
            img.save(buf, "PNG", optimize=True)
            z.writestr(nombre, buf.getvalue())
        for nombre, data in sonidos().items():
            z.writestr(nombre, data)
        if os.path.exists(TEMA):
            z.write(TEMA, "tema.mp3")
        else:
            print(f"ojo: no está {TEMA}: el aplicador va a quedar sin música")
    diseno_cs(gema, os.path.join(carpeta, "Diseno.cs"), edicion, frase_x, frase_w)
    icono(img_ext["zohar"], os.path.join(carpeta, "icono.ico"))
    return arte, os.path.join(carpeta, "Diseno.cs"), os.path.join(carpeta, "icono.ico")


if __name__ == "__main__":
    import sys
    out = os.path.join(ROOT, "work", "publicar", "arte")
    print(generar(sys.argv[1] if len(sys.argv) > 1 else "0.0", out, sys.argv[2] if len(sys.argv) > 2 else "es"))
