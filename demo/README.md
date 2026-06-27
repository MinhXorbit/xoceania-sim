# xOceania finals demo

A pre-rendered demo of the xOceania digital twin for the Harvard Crimson Business
Competition finals. It makes the core story undeniable on stage:

> A pond looks fine all day. Overnight, oxygen quietly falls and crashes below the
> lethal line just before dawn. The farmer only sees it at sunrise, after the loss.
> xOceania's twin saw it coming hours earlier, and when xOceania is allowed to act,
> the crash never happens.

Everything here runs on the validated `xoceania_sim` coupled-ODE model through its
public API. The core model in `src/` is not modified; all demo code lives in `demo/`.

## Regenerate everything (one command)

From the repo root, in a virtualenv with the package installed:

```bash
pip install -e .          # if you have not already
python demo/run_demo.py
```

This writes, into `demo/output/`:

| File | What it is |
| --- | --- |
| `xoceania_demo.mp4` | The animated 48 h story, 1920x1080. The main stage asset. |
| `xoceania_demo.gif` | GIF fallback that plays anywhere, no codec needed. |
| `stills/still_1_crash.png` | The pre-dawn crash with the 5 mg/L stress line and danger zone. |
| `stills/still_2_forecast.png` | The "too late" trough plus the 6h-ahead forecast marker. |
| `stills/still_3_contrast.png` | Do nothing vs xOceania acts, the full story on one chart. |
| `stills/still_4_hero.png` | Clean hero contrast for a title or closing slide. |

The stills are near instant; rendering the full 1920x1080 MP4 plus the GIF is the
slow part (roughly 8 to 10 minutes, since every frame is drawn at full resolution).
You only need to run this when something changes. The pre-rendered files are what
goes on stage.

## Live fallback (run it on stage instead of the video)

`demo/demo_live.ipynb` is a clean, reliable notebook fallback. Open it with the repo
root as the working directory and run **Kernel, Restart and Run All**. It simulates
both ponds and draws the full contrast chart inline in well under 30 seconds, then
embeds the pre-rendered video if it exists. Use this if you would rather run the
twin live than play the file.

## What the demo actually computes

- **Do nothing**: a typical farm that runs paddlewheel aerators on a daytime timer
  (on 08:00-17:00) and shuts them off overnight. Dissolved oxygen slides every night
  and crashes to roughly 2.2 mg/L pre-dawn, below the lethal line.
- **xOceania acts**: the twin rolls the same model forward a few hours from the
  current pond state. The moment that forecast shows DO approaching the 5 mg/L
  stress line, it drives aeration to full and holds the pond above the line. It is
  forecast-driven, not always-on, so it also leaves the aerators off when the night
  is genuinely safe.
- **The 6h-ahead marker** is placed where the twin's forward forecast first predicts
  the breach, six hours before the do-nothing pond actually crosses 5 mg/L. The
  predicted value is printed by `run_demo.py` so the claim is backed by a number.

Both runs use the same config and the same deterministic Mekong Delta weather, so the
only difference between the two traces is the control policy.

## Files

| File | Role |
| --- | --- |
| `xoceania_demo.py` | Simulation engine: config, the two controllers, the forecast, and the hour-by-hour stepping harness. Importable and standalone (`python demo/xoceania_demo.py` prints the key numbers). |
| `render.py` | Turns the two trajectories into the MP4, GIF, and stills, brand-styled on the deck's navy palette. |
| `run_demo.py` | One-command regenerator (calls the two modules above). |
| `demo_live.ipynb` | Live fallback notebook. |

## Notes

- Dependencies are light: numpy, scipy, pandas, matplotlib, gymnasium (already a
  package dependency), plus `imageio-ffmpeg` for the MP4. If no ffmpeg codec is
  available, the GIF is still written and `run_demo.py` says so.
- On-screen text and code use no em dashes, matching the deck style.
- The demo relaxes the ODE solver tolerance (rtol 1e-3) versus the publication
  default (1e-4). This reproduces the same DO trajectory (trough within 0.01 mg/L)
  but runs in seconds instead of tens of seconds, which the live notebook needs.
