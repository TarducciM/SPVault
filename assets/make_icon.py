r"""Icona di SPVault e immagine per la pagina GitHub (social preview), dal disegno descritto qui sotto.

Scrive in assets\:
  app-icon.svg        icona 1024x1024: quadrato arrotondato con sfumatura e, in bianco, la porta
                      tonda di una cassaforte (cerniere a sinistra, pomello dorato a destra) con
                      dentro una freccia verso il basso: i file copiati al sicuro sul PC
  social-preview.svg  immagine 1280x640 per GitHub (Settings > General > Social preview)
  social-preview.png  la stessa in PNG, da caricare su GitHub
  spvault.ico         icona dell'exe, dell'installer e della finestra: 16, 20, 24, 32, 40, 48, 64, 128, 256 px
  spvault.png         256x256, icona della finestra (tk iconphoto)

Le dimensioni da 16 a 48 px hanno un disegno ritoccato (tratti un po' più grossi e allineati ai
pixel; sotto i 24 px niente cerniere e freccia con la punta piena) per restare nitide nella barra
del titolo, nella barra delle applicazioni e sul desktop.

Gli SVG vengono disegnati in PNG da Chrome o Edge tramite Playwright (già una dipendenza dell'app);
Pillow serve per il file .ico e per l'anteprima:  python -m pip install -r requirements-dev.txt
Uso:  python assets\make_icon.py [--preview anteprima.png]
"""

import io
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ASSETS = Path(__file__).resolve().parent
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

TILE = ("#22B98A", "#064A3A")    # sfumatura del quadrato, dall'angolo in alto a sinistra a quello in basso a destra
BANNER = ("#0F2E27", "#061712")  # sfondo della social preview: stessa tinta, molto scura
WHITE = "#ffffff"
GOLD = "#FBBF24"                 # pomello della porta, unico colore di contrasto

# Disegno in unità della viewBox 1024x1024 (quadrato x=y=64, lato 896, raggio 200 come le altre app
# della stessa famiglia).
#   ring   porta: centro, raggio e spessore del cerchio
#   arrow  freccia: x, inizio e punta (y), mezza larghezza e altezza della punta, spessore;
#          solid = punta piena (per le dimensioni più piccole)
#   hinges cerniere: x, centro (y) di ciascuna, mezza lunghezza, spessore; None = senza cerniere
#   knob   pomello dorato: centro e raggio
MASTER = {
    "margin": 64, "radius": 200,
    "ring": (486, 512, 203, 56),
    "arrow": (486, 412, 602, 74, 74, 56), "solid": False,
    "hinges": (258, (412, 612), 34, 52),
    "knob": (751, 512, 46),
}


def pixels(size: int, **p) -> dict:
    """Disegno scritto in pixel della dimensione finale -> unità della viewBox."""
    k = 1024 / size

    def scale(v):
        if isinstance(v, tuple):
            return tuple(scale(x) for x in v)
        return v * k if isinstance(v, (int, float)) and not isinstance(v, bool) else v
    return {name: scale(v) for name, v in p.items()}


# Dimensioni piccole ritoccate a mano, in pixel: bordi del quadrato, del cerchio e della freccia su pixel interi.
SMALL = {
    48: pixels(48, margin=3, radius=9.4, ring=(22.5, 23.5, 10, 3), arrow=(22.5, 18.5, 28.5, 4.5, 4.5, 3),
               solid=False, hinges=(10.5, (19, 28), 1.5, 3), knob=(35.5, 23.5, 2.5)),
    40: pixels(40, margin=2, radius=7.8, ring=(19, 20, 9, 2), arrow=(19, 15, 24.5, 4, 4, 2), solid=False,
               hinges=(8.5, (15.5, 24.5), 1.25, 2.5), knob=(29.75, 20, 2.25)),
    32: pixels(32, margin=2, radius=6.25, ring=(15, 16, 8, 2), arrow=(15, 11.5, 20, 3.5, 3.5, 2), solid=False,
               hinges=(6.5, (12.5, 19.5), 1, 2.5), knob=(25.5, 16, 2)),
    24: pixels(24, margin=1, radius=4.75, ring=(11, 12, 6, 2), arrow=(11, 9, 14.5, 2.5, 2.5, 2), solid=False,
               hinges=(4, (8.5, 15.5), 0.5, 1.5), knob=(19.5, 12, 1.75)),
    20: pixels(20, margin=1, radius=4, ring=(9, 10, 5.25, 1.5), arrow=(9, 6.5, 13.5, 3, 3.5, 2), solid=True,
               hinges=None, knob=(15.75, 10, 1.5)),
    16: pixels(16, margin=1, radius=3.25, ring=(7, 8, 4.25, 1.5), arrow=(7, 4.75, 11, 2.5, 3, 2), solid=True,
               hinges=None, knob=(13, 8, 1.25)),
}


def layout(size: int) -> dict:
    if size in SMALL:
        return SMALL[size]
    margin = round(MASTER["margin"] * size / 1024)  # bordo del quadrato su un pixel intero
    return dict(MASTER, margin=margin * 1024 / size)


def num(v: float) -> str:
    return f"{round(v, 2):g}"


def glyph(p: dict, bg: str, gloss: str, clip: str, indent: str) -> list[str]:
    """Elementi dell'icona (quadrato, riflesso, porta, freccia, pomello), senza <svg> e <defs>."""
    m, r = num(p["margin"]), num(p["radius"])
    side = num(1024 - 2 * p["margin"])
    cx, cy, rr, sw = p["ring"]
    ax, ay0, ay1, aw, ah, asw = p["arrow"]
    kx, ky, kr = p["knob"]
    stroke = f'fill="none" stroke="{WHITE}"'
    lines = [
        "<!-- rounded square -->",
        f'<rect x="{m}" y="{m}" width="{side}" height="{side}" rx="{r}" fill="url(#{bg})"/>',
        f'<rect x="{m}" y="{m}" width="{side}" height="470" fill="url(#{gloss})" clip-path="url(#{clip})"/>',
        "",
        "<!-- vault door on its hinges -->",
        f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{num(rr)}" {stroke} stroke-width="{num(sw)}"/>',
    ]
    if p["hinges"]:
        hx, ys, half, hsw = p["hinges"]
        d = " ".join(f"M{num(hx)} {num(y - half)} V{num(y + half)}" for y in ys)
        lines.append(f'<path d="{d}" {stroke} stroke-width="{num(hsw)}" stroke-linecap="round"/>')
    lines += ["", "<!-- arrow: files copied down into the vault -->"]
    if p["solid"]:
        lines += [f'<path d="M{num(ax)} {num(ay0)} V{num(ay1 - ah)}" {stroke} stroke-width="{num(asw)}"/>',
                  f'<path d="M{num(ax - aw)} {num(ay1 - ah)} H{num(ax + aw)} L{num(ax)} {num(ay1)} Z" '
                  f'fill="{WHITE}"/>']
    else:
        lines.append(f'<path d="M{num(ax)} {num(ay0)} V{num(ay1)} M{num(ax - aw)} {num(ay1 - ah)} '
                     f'L{num(ax)} {num(ay1)} L{num(ax + aw)} {num(ay1 - ah)}" {stroke} '
                     f'stroke-width="{num(asw)}" stroke-linecap="round" stroke-linejoin="round"/>')
    lines += ["", "<!-- handle -->", f'<circle cx="{num(kx)}" cy="{num(ky)}" r="{num(kr)}" fill="{GOLD}"/>']
    return [indent + line if line else "" for line in lines]


def defs(p: dict, bg: str, colors: tuple[str, str], indent: str, gloss_clip=True) -> list[str]:
    lines = [f'<linearGradient id="{bg}" x1="0" y1="0" x2="1" y2="1">',
             f'  <stop offset="0" stop-color="{colors[0]}"/>',
             f'  <stop offset="1" stop-color="{colors[1]}"/>',
             "</linearGradient>"]
    if gloss_clip:
        m, side, r = num(p["margin"]), num(1024 - 2 * p["margin"]), num(p["radius"])
        lines += ['<linearGradient id="gloss" x1="0" y1="0" x2="0" y2="1">',
                  f'  <stop offset="0" stop-color="{WHITE}" stop-opacity="0.16"/>',
                  f'  <stop offset="1" stop-color="{WHITE}" stop-opacity="0"/>',
                  "</linearGradient>",
                  '<clipPath id="clip">',
                  f'  <rect x="{m}" y="{m}" width="{side}" height="{side}" rx="{r}"/>',
                  "</clipPath>"]
    return [indent + line for line in lines]


NOTE = "  <!-- SPVault: written by assets/make_icon.py (change the layout there and run it again) -->"


def icon_svg(p: dict) -> str:
    lines = ['<svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">', NOTE,
             "  <defs>", *defs(p, "bg", TILE, "    "), "  </defs>", "",
             *glyph(p, "bg", "gloss", "clip", "  "),
             "</svg>"]
    return "\n".join(lines) + "\n"


def social_svg() -> str:
    """1280x640 come le altre app della famiglia: sfondo scuro e icona al centro, senza testo."""
    lines = ['<svg viewBox="0 0 1280 640" xmlns="http://www.w3.org/2000/svg">', NOTE,
             "  <defs>",
             *defs(MASTER, "bg", BANNER, "    ", gloss_clip=False),
             *defs(MASTER, "iconBg", TILE, "    "),
             "  </defs>", "",
             '  <rect width="1280" height="640" fill="url(#bg)"/>', "",
             '  <svg x="450" y="130" width="380" height="380" viewBox="0 0 1024 1024">',
             *glyph(MASTER, "iconBg", "gloss", "clip", "    "),
             "  </svg>",
             "</svg>"]
    return "\n".join(lines) + "\n"


# --- immagini

class Renderer:
    """Chrome o Edge senza finestra: disegna un SVG in PNG a una dimensione esatta."""

    def __enter__(self):
        self.pw = sync_playwright().start()
        for channel in ("chrome", "msedge"):
            try:
                self.browser = self.pw.chromium.launch(channel=channel)
                break
            except Exception:  # canale non installato: si prova il successivo
                continue
        else:
            self.pw.stop()
            raise SystemExit("Serve Google Chrome o Microsoft Edge")
        self.page = self.browser.new_page(device_scale_factor=1)
        return self

    def __exit__(self, *exc):
        self.browser.close()
        self.pw.stop()

    def png(self, svg: str, width: int, height: int) -> Image.Image:
        self.page.set_viewport_size({"width": width, "height": height})
        sized = svg.replace("<svg ", f'<svg width="{width}" height="{height}" ', 1)
        self.page.set_content(f'<html><body style="margin:0">{sized}</body></html>')
        shot = self.page.screenshot(omit_background=True)
        return Image.open(io.BytesIO(shot)).convert("RGBA")


def ico_bitmap(im: Image.Image) -> bytes:
    """Immagine BMP a 32 bit (BGRA + maschera AND) come nei file .ico classici."""
    w, h = im.size
    b, g, r, a = (im.getchannel(c) for c in "BGRA")
    rows = Image.merge("RGBA", (b, g, r, a)).tobytes()
    stride = w * 4
    xor = b"".join(rows[y * stride:(y + 1) * stride] for y in reversed(range(h)))  # righe dal basso
    mask_stride = (w + 31) // 32 * 4
    mask = bytearray()
    for y in reversed(range(h)):  # bit a 1 = pixel trasparente
        line = bytearray(mask_stride)
        for x in range(w):
            if a.getpixel((x, y)) == 0:
                line[x // 8] |= 0x80 >> (x % 8)
        mask += line
    header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, len(xor) + len(mask), 0, 0, 0, 0)
    return header + xor + bytes(mask)


def write_ico(path: Path, images: list[Image.Image]):
    """File .ico con una immagine per dimensione: BMP fino a 128 px, PNG per 256 px (come Windows)."""
    blobs = []
    for im in images:
        if im.width >= 256:
            buf = io.BytesIO()
            im.save(buf, "PNG", optimize=True)
            blobs.append(buf.getvalue())
        else:
            blobs.append(ico_bitmap(im))
    out = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    offset = 6 + 16 * len(images)
    for im, blob in zip(images, blobs, strict=True):
        out += struct.pack("<BBBBHHII", im.width % 256, im.height % 256, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    for blob in blobs:
        out += blob
    path.write_bytes(bytes(out))


def preview(ico: Path, social: Path) -> Image.Image:
    """Tutte le dimensioni del .ico su sfondo chiaro e scuro, 16/24/32 px ingranditi al 400%,
    e la social preview a metà grandezza."""
    with Image.open(ico) as f:
        icons = {s: f.ico.getimage((s, s)).convert("RGBA") for s in ICO_SIZES}
    font = ImageFont.load_default(14)
    width, band = 1280, 310
    sheet = Image.new("RGB", (width, band * 2 + 360), "#ffffff")
    draw = ImageDraw.Draw(sheet)
    for i, bg in enumerate(("#f3f3f3", "#202020")):
        top = i * band
        draw.rectangle([0, top, width, top + band], fill=bg)
        ink = "#606060" if i == 0 else "#a0a0a0"
        x = 20
        for s in reversed(ICO_SIZES):
            sheet.paste(icons[s], (x, top + 20), icons[s])
            draw.text((x, top + 296), str(s), fill=ink, font=font, anchor="ls")
            x += s + 22
        x += 10
        for s in (16, 24, 32):
            zoom = icons[s].resize((s * 4, s * 4), Image.Resampling.NEAREST)
            sheet.paste(zoom, (x, top + 20), zoom)
            draw.text((x, top + 20 + s * 4 + 20), f"{s} x4", fill=ink, font=font, anchor="ls")
            x += s * 4 + 22
    with Image.open(social) as banner:
        sheet.paste(banner.convert("RGB").resize((640, 320), Image.Resampling.LANCZOS), (20, band * 2 + 20))
    return sheet


def main(argv: list[str]):
    (ASSETS / "app-icon.svg").write_text(icon_svg(MASTER), encoding="utf-8", newline="\n")
    (ASSETS / "social-preview.svg").write_text(social_svg(), encoding="utf-8", newline="\n")
    with Renderer() as r:
        icons = [r.png(icon_svg(layout(s)), s, s) for s in ICO_SIZES]
        social = r.png(social_svg(), 1280, 640).convert("RGB")
    write_ico(ASSETS / "spvault.ico", icons)
    icons[-1].save(ASSETS / "spvault.png", optimize=True)
    social.save(ASSETS / "social-preview.png", optimize=True)
    if "--preview" in argv:
        target = Path(argv[argv.index("--preview") + 1])
        preview(ASSETS / "spvault.ico", ASSETS / "social-preview.png").save(target)
        print(f"Anteprima: {target}")
    print("OK: assets\\app-icon.svg, social-preview.svg/.png, spvault.ico, spvault.png")


if __name__ == "__main__":
    main(sys.argv[1:])
