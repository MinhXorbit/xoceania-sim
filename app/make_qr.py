"""Generate a branded QR code that points at the hosted xOceania app.

Usage:
    python app/make_qr.py "https://your-app.lovable.app"
    python app/make_qr.py "https://your-app.lovable.app" --no-logo

Writes app/qr/xoceania_qr.png (and .svg). Re-run with your real Lovable URL once
the site is live. High error correction (level H) is used so the centre logo does
not stop the code from scanning.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import segno

HERE = Path(__file__).resolve().parent
NAVY = "#071726"
WHITE = "#ffffff"


def add_center_logo(png_path: Path, logo_path: Path) -> None:
    """Overlay the brand logo on a navy rounded badge in the QR centre."""
    from PIL import Image, ImageDraw

    qr = Image.open(png_path).convert("RGBA")
    w, h = qr.size
    badge = int(w * 0.24)
    pad = int(badge * 0.16)

    plate = Image.new("RGBA", (badge, badge), (0, 0, 0, 0))
    d = ImageDraw.Draw(plate)
    d.rounded_rectangle([0, 0, badge - 1, badge - 1], radius=int(badge * 0.22),
                        fill=NAVY)

    logo = Image.open(logo_path).convert("RGBA")
    inner = badge - 2 * pad
    lw, lh = logo.size
    scale = min(inner / lw, inner / lh)
    logo = logo.resize((max(1, int(lw * scale)), max(1, int(lh * scale))), Image.LANCZOS)
    lx = (badge - logo.size[0]) // 2
    ly = (badge - logo.size[1]) // 2
    plate.alpha_composite(logo, (lx, ly))

    qr.alpha_composite(plate, ((w - badge) // 2, (h - badge) // 2))
    qr.save(png_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="URL the QR should open (the hosted app)")
    ap.add_argument("--out", default=str(HERE / "qr" / "xoceania_qr.png"))
    ap.add_argument("--logo", default=str(HERE / "assets" / "logo.png"))
    ap.add_argument("--no-logo", action="store_true", help="plainest, most scannable")
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    qr = segno.make(args.url, error="h")
    qr.save(str(out), scale=16, border=4, dark=NAVY, light=WHITE)
    qr.save(str(out.with_suffix(".svg")), scale=16, border=4, dark=NAVY, light=WHITE)

    if not args.no_logo and Path(args.logo).exists():
        add_center_logo(out, Path(args.logo))

    print(f"QR -> {out}")
    print(f"QR -> {out.with_suffix('.svg')}")
    print(f"     encodes: {args.url}")


if __name__ == "__main__":
    main()
