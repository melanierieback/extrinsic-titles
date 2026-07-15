#!/usr/bin/env python3
"""Typeset the book title onto the cover artwork, in the NEC house style.

The finished cover in `attached_assets/extrinsic-titles-cover.png` is the raw
illustration (`attached_assets/extrinsic-titles-cover-art.png`, a text-free
gold-on-navy scales emblem) with the title lettering composited on top, so the
title is crisp and correct rather than AI-rendered. This mirrors the sibling
readers, whose covers carry the title in glowing gold serif at the top with an
italic subtitle beneath.

Usage:
    python3 tools/title_cover.py            # re-typesets from the stored art
    python3 tools/title_cover.py --src NEW_ART.png

After running, refresh the Open Graph card:
    python3 tools/make_placeholder_art.py --og-only
"""
import argparse
import pathlib
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "attached_assets"
ART = ASSETS / "extrinsic-titles-cover-art.png"     # raw, text-free illustration
COVER = ASSETS / "extrinsic-titles-cover.png"        # titled cover the reader uses

LORA = "/usr/share/fonts/truetype/google-fonts/Lora-Variable.ttf"
LORA_IT = "/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf"

GOLD_TEXT = (242, 208, 116)
GOLD_GLOW = (206, 160, 60)
GOLD_SOFT = (232, 198, 112)

TAG = "A WORKING MANUSCRIPT"
TITLE = "EXTRINSIC TITLES"
SUB1 = "Capital, Risk, and the Sin of Usury"
SUB2 = "The Forgotten History of the Extrinsic Titles"


def font(path, size, weight=400):
    f = ImageFont.truetype(path, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def build(src: pathlib.Path, out: pathlib.Path):
    im = Image.open(src).convert("RGBA")
    W, H = im.size
    cx = W / 2

    # gentle feathered scrims (top + bottom) so lettering stays legible over stars
    scrim = Image.new("L", (W, H), 0)
    sp = scrim.load()
    for y in range(H):
        a = 0
        if y < 250:
            a = int(95 * (1 - y / 250))
        elif y > 1040:
            a = int(120 * ((y - 1040) / (H - 1040)))
        if a:
            for x in range(W):
                sp[x, y] = a
    im = Image.composite(Image.new("RGBA", (W, H), (3, 5, 14, 255)), im, scrim)

    def tracked(draw, y, text, fnt, fill, tracking):
        widths = [draw.textlength(ch, font=fnt) for ch in text]
        total = sum(widths) + tracking * (len(text) - 1)
        x = cx - total / 2
        for ch, wd in zip(text, widths):
            draw.text((x, y), ch, font=fnt, fill=fill)
            x += wd + tracking

    def glow_text(base, y, text, fnt, tracking, glow_r=12, glow_a=210):
        gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        tracked(ImageDraw.Draw(gl), y, text, fnt, GOLD_GLOW + (glow_a,), tracking)
        base.alpha_composite(gl.filter(ImageFilter.GaussianBlur(glow_r)))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        tracked(ImageDraw.Draw(sh), y, text, fnt, GOLD_TEXT + (255,), tracking)
        base.alpha_composite(sh)

    def center(base, y, text, fnt, fill):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((cx, y), text, font=fnt, fill=fill, anchor="mm")
        base.alpha_composite(layer)

    def divider(draw, y, half=190):
        draw.line([cx - half, y, cx - 24, y], fill=GOLD_GLOW + (170,), width=2)
        draw.line([cx + 24, y, cx + half, y], fill=GOLD_GLOW + (170,), width=2)
        draw.polygon([(cx, y - 9), (cx + 9, y), (cx, y + 9), (cx - 9, y)],
                     fill=GOLD_TEXT + (210,))

    # top: tag + title + divider
    tracked(ImageDraw.Draw(im, "RGBA"), 52, TAG, font(LORA, 26, 700), GOLD_SOFT + (210,), 12)
    glow_text(im, 100, TITLE, font(LORA, 78, 700), 8)
    divider(ImageDraw.Draw(im, "RGBA"), 210)

    # bottom: divider + subtitle
    d = ImageDraw.Draw(im, "RGBA")
    divider(d, 1150, half=210)
    center(im, 1212, SUB1, font(LORA, 46, 600), GOLD_TEXT + (255,))
    center(im, 1274, SUB2, font(LORA_IT, 35), GOLD_SOFT + (235,))

    im.convert("RGB").save(out, "PNG", optimize=True)
    print(f"wrote {out} ({out.stat().st_size:,} bytes, {im.size[0]}x{im.size[1]})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ART), help="raw cover artwork (text-free)")
    ap.add_argument("--out", default=str(COVER), help="titled cover output")
    args = ap.parse_args()
    build(pathlib.Path(args.src), pathlib.Path(args.out))
