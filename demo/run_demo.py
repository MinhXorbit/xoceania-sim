"""xOceania HCBC finals demo: one-command regenerator.

Run from the repo root, in a venv where the package is installed:

    pip install -e .
    python demo/run_demo.py

Writes, under demo/output/:
    xoceania_demo.mp4        the animated 48 h story (1920x1080)
    xoceania_demo.gif        GIF fallback (no codec needed to play)
    stills/still_1_crash.png        the pre-dawn crash with the stress line
    stills/still_2_forecast.png     the "too late" trough + 6h forecast marker
    stills/still_3_contrast.png     do nothing vs xOceania acts
    stills/still_4_hero.png         clean hero contrast for a title slide

Everything is pre-rendered so nothing has to run live on stage. The simulation
uses only the public xoceania_sim API; the core model in src/ is untouched.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow `python demo/run_demo.py` from the repo root (so `import render` works).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import xoceania_demo as demo
import render


def main() -> int:
    t0 = time.time()
    print("=" * 70)
    print("xOceania finals demo: regenerating video, GIF and stills")
    print("=" * 70)

    print("[1/3] Simulating both ponds (do nothing vs xOceania acts) ...")
    data = demo.compute_demo()
    b, x = data.do_nothing, data.xoceania
    print(f"      Do nothing : DO troughs at {data.trough_do:.2f} mg/L "
          f"({data.trough_time:.0f} h, pre-dawn).")
    print(f"      xOceania   : DO never drops below {x.DO.min():.2f} mg/L.")
    if data.forecast_time is not None:
        print(f"      Forecast   : twin sees the crash {data.forecast_lead_h:.0f} h "
              f"early (predicted min DO {data.forecast_value:.2f} mg/L at "
              f"{data.forecast_time:.0f} h).")

    print("[2/3] Writing high-resolution stills ...")
    stills = render.render_stills(data)
    for p in stills:
        print(f"      {p.relative_to(render.REPO_ROOT)}")

    print("[3/3] Rendering the animation (MP4 + GIF). This takes a minute ...")
    written = render.write_video(data)
    for kind, p in written.items():
        print(f"      {kind.upper():3s}: {p.relative_to(render.REPO_ROOT)}")

    if "mp4" not in written:
        print("      NOTE: MP4 codec was unavailable; the GIF is the fallback.")

    print("-" * 70)
    print(f"Done in {time.time() - t0:.0f} s. Open demo/output/xoceania_demo.mp4")
    print("To regenerate: python demo/run_demo.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
