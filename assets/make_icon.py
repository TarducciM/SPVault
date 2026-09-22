r"""Icona di SPVault e immagine per la pagina GitHub (social preview), dal disegno descritto qui sotto.

Scrive in assets\:
  app-icon.svg        icona 1024x1024: quadrato arrotondato con sfumatura e, in bianco, una nuvola
                      da cui scende una freccia dorata dentro un vassoio: i file dal cloud al
                      sicuro sul PC
  social-preview.svg  immagine 1280x640 per GitHub (Settings > General > Social preview)
  social-preview.png  la stessa in PNG, da caricare su GitHub
  spvault.ico         icona dell'exe, dell'installer e della finestra: 16, 20, 24, 32, 40, 48, 64, 128, 256 px
  spvault.png         256x256, icona della finestra (tk iconphoto)

Le dimensioni da 16 a 48 px hanno tratti più grossi e il simbolo un po' più grande (tabella SMALL)
per restare nitide nella barra del titolo, nella barra delle applicazioni e sul desktop.

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
GOLD = "#FBBF24"                 # freccia, unico colore di contrasto

# Disegno in unità della viewBox 1024x1024 (quadrato x=y=64, lato 896, raggio 200 come le altre app
# della stessa famiglia). Simbolo: una nuvola (contorno bianco a spessore costante, aperta sul fondo)
# da cui scende una freccia dorata dentro un vassoio bianco: i file dal cloud al sicuro sul PC.
#   lobes  nuvola: tre cerchi (x, y, raggio); la base piatta va dal primo all'ultimo
#   base   y della base della nuvola; gap = apertura sul fondo (x1, x2) da cui esce la freccia
#   arrow  freccia: x, inizio e punta (y), mezza larghezza della punta
#   tray   vassoio: x sinistra/destra, y dei bordi alti, y del fondo, raggio degli angoli
#   stroke spessore dei tratti; weight lo moltiplica (più grosso nelle dimensioni piccole)
#   zoom   scala del simbolo attorno al centro (0.86: occupa circa due terzi del quadrato, come le
#          altre app); nelle dimensioni piccole SMALL lo moltiplica per ingrandirlo un po'
#   shift  spostamento verso il basso, per centrarlo otticamente (la nuvola pesa in alto)
MASTER = {
    "margin": 64, "radius": 200,
    "lobes": ((354, 402, 118), (502, 302, 170), (650, 382, 138)), "base": 520, "gap": (440, 584),
    "arrow": (512, 400, 670, 72),
    "tray": (300, 724, 676, 790, 48),
    "stroke": 46, "weight": 1.0, "zoom": 0.86, "shift": 34,
}

# Dimensioni piccole: bordo del quadrato su pixel interi, tratti più grossi e simbolo un po' più grande.
SMALL = {
    48: dict(margin=3, weight=1.1, zoom=1.02),
    40: dict(margin=2, weight=1.15, zoom=1.03),
    32: dict(margin=2, weight=1.25, zoom=1.04),
    24: dict(margin=1, weight=1.4, zoom=1.06),
    20: dict(margin=1, weight=1.55, zoom=1.08),
    16: dict(margin=1, weight=1.7, zoom=1.1),
}


def layout(size: int) -> dict:
    tuned = SMALL.get(size, {})
    margin = tuned.get("margin", round(MASTER["margin"] * size / 1024))  # bordo su un pixel intero
    margin_units = margin * 1024 / size
    radius = MASTER["radius"] * (1024 - 2 * margin_units) / (1024 - 2 * MASTER["margin"])
    zoom = MASTER["zoom"] * tuned.get("zoom", 1)
    return dict(MASTER, **{k: v for k, v in tuned.items() if k not in ("margin", "zoom")},
                margin=margin_units, radius=radius, zoom=zoom)


def num(v: float) -> str:
    return f"{round(v, 2):g}"


def glyph(p: dict, bg: str, gloss: str, clip: str, indent: str) -> list[str]:
    """Elementi dell'icona (quadrato, riflesso, nuvola, freccia, vassoio), senza <svg> e <defs>."""
    m, r = num(p["margin"]), num(p["radius"])
    side = num(1024 - 2 * p["margin"])
    t = p["stroke"] * p["weight"]
    (x1, _, _), _, (x2, _, _) = p["lobes"]
    base, (g1, g2) = p["base"], p["gap"]
    ax, ay0, ay1, head = p["arrow"]
    tl, tr, ttop, tbot, trad = p["tray"]
    z = p["zoom"]
    outer = "".join(f'<circle cx="{num(x)}" cy="{num(y)}" r="{num(rr)}"/>' for x, y, rr in p["lobes"])
    top_left, top = p["lobes"][0][1], p["lobes"][1][1]  # base piena: dal lobo sinistro in giù
    outer += (f'<rect x="{num(x1)}" y="{num(top_left)}" width="{num(x2 - x1)}" '
              f'height="{num(base - top_left)}"/>')
    inner = "".join(f'<circle cx="{num(x)}" cy="{num(y)}" r="{num(rr - t)}"/>' for x, y, rr in p["lobes"])
    inner += (f'<rect x="{num(x1)}" y="{num(top)}" width="{num(x2 - x1)}" '
              f'height="{num(base - t - top)}"/>')
    round_caps = "".join(f'<circle cx="{num(x)}" cy="{num(base - t / 2)}" r="{num(t / 2)}" fill="{WHITE}"/>'
                         for x in (g1, g2))
    line = 'fill="none" stroke-linecap="round" stroke-linejoin="round"'
    lines = [
        "<!-- rounded square -->",
        f'<rect x="{m}" y="{m}" width="{side}" height="{side}" rx="{r}" fill="url(#{bg})"/>',
        f'<rect x="{m}" y="{m}" width="{side}" height="470" fill="url(#{gloss})" clip-path="url(#{clip})"/>',
        "",
        f'<g transform="translate(512 {num(512 + p["shift"])}) scale({num(z)}) translate(-512 -512)">',
        "  <!-- cloud: outline of three circles on a flat base, open at the bottom -->",
        '  <mask id="cloud" maskUnits="userSpaceOnUse" x="0" y="0" width="1024" height="1024">',
        f'    <g fill="#fff">{outer}</g>',
        f'    <g fill="#000">{inner}</g>',
        f'    <rect x="{num(g1)}" y="{num(base - t - 40)}" width="{num(g2 - g1)}" height="{num(t + 80)}" fill="#000"/>',
        "  </mask>",
        f'  <rect width="1024" height="1024" fill="{WHITE}" mask="url(#cloud)"/>',
        f"  {round_caps}",
        "",
        "  <!-- arrow: files coming down from the cloud -->",
        f'  <path d="M{num(ax)} {num(ay0)} V{num(ay1)} M{num(ax - head)} {num(ay1 - head)} L{num(ax)} {num(ay1)} '
        f'L{num(ax + head)} {num(ay1 - head)}" {line} stroke="{GOLD}" stroke-width="{num(t * 50 / 46)}"/>',
        "",
        "  <!-- tray: safe on your PC -->",
        f'  <path d="M{num(tl)} {num(ttop)} V{num(tbot - trad)} Q{num(tl)} {num(tbot)} {num(tl + trad)} {num(tbot)} '
        f'H{num(tr - trad)} Q{num(tr)} {num(tbot)} {num(tr)} {num(tbot - trad)} V{num(ttop)}" {line} '
        f'stroke="{WHITE}" stroke-width="{num(t)}"/>',
        "</g>",
    ]
    return [indent + ln if ln else "" for ln in lines]


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
