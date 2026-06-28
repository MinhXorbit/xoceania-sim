"""Export real digital-twin trajectories for the web app.

Runs the actual xoceania_sim coupled-ODE model (via demo/xoceania_demo.py) for
two policies over one night, and writes app/assets/twin_data.js so the app plays
genuine model output instead of hand-drawn curves:

  do_nothing  - timer aeration (off overnight): DO crashes pre-dawn
  autonomous  - the forecast-driven controller: DO held above the stress line

We take a 24 h window starting at 18:00 so the pre-dawn crash lands mid-view.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "demo"))
import xoceania_demo as twin  # noqa: E402

WIN_START, WIN_END = 18.0, 42.0  # hours of the 48 h run -> 18:00 to 18:00 next day


def main() -> None:
    data = twin.compute_demo()
    b, x = data.do_nothing, data.xoceania
    t = b.t

    mask = (t >= WIN_START - 1e-6) & (t <= WIN_END + 1e-6)
    hours = [round(float(ti - WIN_START), 2) for ti in t[mask]]
    do_nothing = [round(float(v), 2) for v in b.DO[mask]]
    autonomous = [round(float(v), 2) for v in x.DO[mask]]

    i = int(np.argmin(do_nothing))
    out = {
        "source": "xoceania_sim coupled-ODE pond model (Paper 1)",
        "clockStart": int(WIN_START),
        "threshold": twin.STRESS_THRESHOLD,
        "forecastLeadH": round(float(data.forecast_lead_h or 6.0), 1),
        "hours": hours,
        "do_nothing": do_nothing,
        "autonomous": autonomous,
        "trough": {"t": hours[i], "do": do_nothing[i]},
    }

    js = "window.XO_TWIN = " + json.dumps(out, separators=(",", ":")) + ";\n"
    out_path = REPO / "app" / "assets" / "twin_data.js"
    out_path.write_text(js)
    print(f"wrote {out_path} ({len(hours)} points)")
    print(f"  do_nothing trough {out['trough']['do']} mg/L at t={out['trough']['t']} h")
    print(f"  autonomous min   {min(autonomous)} mg/L")


if __name__ == "__main__":
    main()
