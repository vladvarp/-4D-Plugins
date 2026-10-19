#!/usr/bin/env python3
"""Генератор иконок Cinema 4D. PNG пишется сюда же, в c4d_icons/.
В .pyp base64 не вставлять — пользователь конвертирует сам.
Стиль: web/ICON_STYLE_GUIDE.md
"""
import os
from PIL import Image, ImageDraw

SIZE = 64
SCALE = 4
CANVAS = SIZE * SCALE
OUT = os.path.dirname(os.path.abspath(__file__))

BG     = (0, 0, 0, 0)
CYAN   = (0, 200, 255, 255)
CYAN_L = (100, 220, 255, 255)
CYAN_D = (0, 140, 200, 255)
WHITE  = (230, 235, 240, 255)
ORANGE = (255, 160, 50, 255)
GREEN  = (80, 220, 130, 255)
RED_L  = (255, 100, 100, 255)
YELLOW = (255, 210, 60, 255)
GRAY   = (120, 130, 145, 255)
GRAY_L = (170, 180, 195, 255)
GRAY_D = (70, 75, 85, 255)


def s(v):
    return int(v * SCALE)


def make():
    return Image.new("RGBA", (CANVAS, CANVAS), BG)


def save(img, name):
    path = os.path.join(OUT, name if name.lower().endswith(".png") else name + ".png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.resize((SIZE, SIZE), Image.LANCZOS).save(path, "PNG")
    print("  OK", os.path.relpath(path, OUT))


def icon_tessera():
    """Облицовка: доски разной длины + акцентный шеврон."""
    img = make()
    d = ImageDraw.Draw(img)
    # основание
    d.rounded_rectangle([s(6), s(10), s(58), s(54)], radius=s(3), outline=CYAN, width=s(3))
    # подложка
    d.rectangle([s(10), s(44), s(54), s(50)], fill=CYAN_D)
    # планки разной длины
    rows = [
        (10, 14, 28, 20),
        (30, 14, 54, 20),
        (10, 22, 22, 28),
        (24, 22, 54, 28),
        (10, 30, 40, 36),
        (42, 30, 54, 36),
        (10, 38, 18, 44),
        (20, 38, 54, 44),
    ]
    for i, box in enumerate(rows):
        fill = ORANGE if i in (3, 5) else None
        d.rectangle([s(box[0]), s(box[1]), s(box[2]), s(box[3])],
                    fill=fill, outline=CYAN if fill is None else ORANGE, width=s(2))
    save(img, "Tessera.png")


def main():
    print("Generating 64x64 icons -> c4d_icons/ ...")
    for fn in [icon_tessera]:
        fn()
    print("Done.")


if __name__ == "__main__":
    main()
