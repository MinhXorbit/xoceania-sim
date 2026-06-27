"""xOceania HCBC finals demo: renderer.

Turns the two simulated trajectories (see xoceania_demo.py) into the finals
deliverables, all brand-styled on the deck's navy palette:

  - output/xoceania_demo.mp4    the 30-45 s animated story (1920x1080)
  - output/xoceania_demo.gif    a GIF fallback if no projector audio/codec
  - output/stills/*.png         high resolution key frames for slides / backup

The animation lands these beats in order:
  1. The DO curve draws in across a 48 h window, with the 5 mg/L stress line.
  2. The pre-dawn crash dips below the line; the danger zone shades in.
  3. "Farmer sees gasping fish at dawn, too late" annotates the trough.
  4. A marker hours before the crash: "xOceania forecasts the crash 6h ahead".
  5. "Do nothing" vs "xOceania acts": the acted trace holds above the line. Hold.

No em dashes in any on-screen text (brand style).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch

from xoceania_demo import (
    DemoData,
    compute_demo,
    STRESS_THRESHOLD,
    LETHAL_THRESHOLD,
    FORECAST_HORIZON_H,
    DEMO_HOURS,
)

# --- Brand palette (match the deck exactly) --------------------------------
BG_NAVY = "#071726"
PANEL = "#0E2336"
TEAL = "#2BC4D4"     # primary accent
BRIGHT = "#5EEAD4"   # bright highlight
ORANGE = "#F0734A"   # danger / threshold / loss
WHITE = "#FFFFFF"
MUTED = "#A6BBC8"

# Semantic trace colors: the failing pond is the brand "loss" orange, the
# xOceania-controlled pond is the bright teal hero. Strong hue separation so the
# crash-vs-holds contrast reads instantly from the back of a room.
DO_NOTHING_COLOR = ORANGE
ACTS_COLOR = BRIGHT
THRESHOLD_COLOR = "#FFC14D"  # warm amber, distinct from the orange loss trace

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
STILLS_DIR = OUTPUT_DIR / "stills"
LOGO_PATH = REPO_ROOT.parent / "xOceania Logo Dark.png"

# Pick a clean sans that exists on the box (Arial/Helvetica/DejaVu Sans).
for _f in ("Arial", "Helvetica", "Helvetica Neue", "DejaVu Sans"):
    if any(_f.lower() in (f.name.lower()) for f in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = _f
        break
plt.rcParams["font.size"] = 15
plt.rcParams["text.color"] = WHITE
plt.rcParams["axes.edgecolor"] = MUTED

FIG_W_IN, FIG_H_IN, DPI = 19.2, 10.8, 100  # -> 1920 x 1080


# --- Helpers ---------------------------------------------------------------

def _load_logo() -> Optional[np.ndarray]:
    """Load the dark-background logo as RGBA, keying out navy if alpha is flat."""
    if not LOGO_PATH.exists():
        return None
    img = plt.imread(str(LOGO_PATH))
    img = np.array(img, dtype=float)
    if img.max() > 1.0:
        img = img / 255.0
    if img.ndim == 2:  # grayscale -> RGB
        img = np.stack([img] * 3, axis=-1)
    if img.shape[-1] == 3:  # add alpha
        img = np.concatenate([img, np.ones(img.shape[:2] + (1,))], axis=-1)
    # If alpha is essentially opaque everywhere, key out the dark navy backdrop
    if img[..., 3].min() > 0.98:
        r, g, b = img[..., 0], img[..., 1], img[..., 2]
        navy = (r < 0.20) & (g < 0.30) & (b < 0.40)
        img[..., 3] = np.where(navy, 0.0, img[..., 3])
    return img


def _dawn_hours(hours: float) -> list[float]:
    """Approximate sunrise hours across the window (Mekong, ~06:00)."""
    return [d * 24.0 + 6.0 for d in range(int(hours // 24) + 1)]


def _style_axes(ax) -> None:
    ax.set_facecolor(PANEL)
    ax.set_xlim(0, DEMO_HOURS)
    ax.set_ylim(0, 9.5)
    ax.set_xticks(np.arange(0, DEMO_HOURS + 1, 6))
    ax.set_xlabel("Hours into the pond cycle", color=MUTED, fontsize=16)
    ax.set_ylabel("Dissolved oxygen (mg/L)", color=MUTED, fontsize=16)
    ax.tick_params(colors=MUTED, labelsize=13)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(MUTED)
    ax.grid(True, color="#16304a", linewidth=0.8, alpha=0.7)


def _night_shading(ax, hours: float) -> None:
    """Shade night (roughly 18:00-06:00) very subtly to anchor 'pre-dawn'."""
    n_days = int(hours // 24) + 1
    for d in range(n_days + 1):
        start = d * 24.0 + 18.0
        end = start + 12.0
        ax.axvspan(max(0, start), min(hours, end), color="#04101c", alpha=0.55, lw=0)
    for dawn in _dawn_hours(hours):
        if 0 < dawn < hours:
            ax.axvline(dawn, color=MUTED, ls=":", lw=1.0, alpha=0.35)
            ax.text(dawn, 9.15, "dawn", color=MUTED, fontsize=11, ha="center", alpha=0.7)


def _place_logo(fig) -> None:
    logo = _load_logo()
    if logo is None:
        fig.text(0.985, 0.045, "xOceania", color=BRIGHT, fontsize=20,
                 ha="right", va="bottom", fontweight="bold")
        return
    h, w = logo.shape[:2]
    aspect = w / h
    lw = 0.16
    lh = lw / aspect * (FIG_W_IN / FIG_H_IN)
    ax_logo = fig.add_axes([0.845, 0.90, lw, lh], zorder=10)
    ax_logo.imshow(logo)
    ax_logo.axis("off")


def _interp(t: np.ndarray, y: np.ndarray, factor: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """Smoothly upsample a trace for drawing."""
    tt = np.linspace(t[0], t[-1], (len(t) - 1) * factor + 1)
    yy = np.interp(tt, t, y)
    return tt, yy


# --- Static frame composition ----------------------------------------------

def _base_figure() -> tuple[plt.Figure, plt.Axes]:
    fig = plt.figure(figsize=(FIG_W_IN, FIG_H_IN), dpi=DPI)
    fig.patch.set_facecolor(BG_NAVY)
    ax = fig.add_axes([0.075, 0.12, 0.88, 0.74])
    _style_axes(ax)
    fig.text(0.075, 0.93, "A pond looks fine all day. Overnight, oxygen quietly crashes.",
             color=WHITE, fontsize=24, fontweight="bold", ha="left", va="center")
    fig.text(0.075, 0.885, "48 hours in a Mekong Delta vannamei shrimp pond",
             color=MUTED, fontsize=15, ha="left", va="center")
    _place_logo(fig)
    return fig, ax


def _threshold(ax) -> None:
    ax.axhline(STRESS_THRESHOLD, color=THRESHOLD_COLOR, ls="--", lw=2.2, alpha=0.95)
    ax.text(0.4, STRESS_THRESHOLD + 0.15, "Stress line, 5 mg/L",
            color=THRESHOLD_COLOR, fontsize=14, va="bottom", fontweight="bold")


def _danger_fill(ax, t, y):
    ax.fill_between(t, y, STRESS_THRESHOLD, where=(y < STRESS_THRESHOLD),
                    color=ORANGE, alpha=0.28, lw=0, interpolate=True)


def build_contrast_figure(data: DemoData):
    """Build and return the full-story contrast figure (do nothing vs acts).

    Shared by the still renderer and the live fallback notebook so both show
    exactly the same frame. Caller is responsible for showing or saving it.
    """
    b, x = data.do_nothing, data.xoceania
    tb, yb = _interp(b.t, b.DO)
    tx, yx = _interp(x.t, x.DO)
    fig, ax = _base_figure()
    _night_shading(ax, DEMO_HOURS)
    _threshold(ax)
    ax.plot(tb, yb, color=DO_NOTHING_COLOR, lw=3.2, label="Do nothing")
    _danger_fill(ax, tb, yb)
    ax.plot(tx, yx, color=ACTS_COLOR, lw=3.8, label="xOceania acts")
    _annotate_too_late(ax, data)
    _forecast_marker(ax, data)
    _contrast_legend(ax)
    return fig, ax


def render_stills(data: DemoData) -> list[Path]:
    """Write the key still frames as high resolution PNGs."""
    STILLS_DIR.mkdir(parents=True, exist_ok=True)
    b, x = data.do_nothing, data.xoceania
    tb, yb = _interp(b.t, b.DO)
    tx, yx = _interp(x.t, x.DO)
    paths: list[Path] = []

    danger_fill = _danger_fill

    # Still 1: the crash, threshold + danger zone.
    fig, ax = _base_figure()
    _night_shading(ax, DEMO_HOURS)
    _threshold(ax)
    ax.plot(tb, yb, color=DO_NOTHING_COLOR, lw=3.4, label="Do nothing")
    danger_fill(ax, tb, yb)
    ax.scatter([data.trough_time], [data.trough_do], color=ORANGE, s=90, zorder=6)
    fig.savefig(STILLS_DIR / "still_1_crash.png", facecolor=BG_NAVY)
    paths.append(STILLS_DIR / "still_1_crash.png")
    plt.close(fig)

    # Still 2: annotation + 6h forecast marker.
    fig, ax = _base_figure()
    _night_shading(ax, DEMO_HOURS)
    _threshold(ax)
    ax.plot(tb, yb, color=DO_NOTHING_COLOR, lw=3.4)
    danger_fill(ax, tb, yb)
    _annotate_too_late(ax, data)
    _forecast_marker(ax, data)
    fig.savefig(STILLS_DIR / "still_2_forecast.png", facecolor=BG_NAVY)
    paths.append(STILLS_DIR / "still_2_forecast.png")
    plt.close(fig)

    # Still 3: the contrast, do nothing vs xOceania acts.
    fig, ax = build_contrast_figure(data)
    fig.savefig(STILLS_DIR / "still_3_contrast.png", facecolor=BG_NAVY)
    paths.append(STILLS_DIR / "still_3_contrast.png")
    plt.close(fig)

    # Still 4: clean hero contrast (no clutter) for a title slide.
    fig, ax = _base_figure()
    _night_shading(ax, DEMO_HOURS)
    _threshold(ax)
    ax.plot(tb, yb, color=DO_NOTHING_COLOR, lw=3.0, alpha=0.85, label="Do nothing")
    danger_fill(ax, tb, yb)
    ax.plot(tx, yx, color=ACTS_COLOR, lw=4.2, label="xOceania acts")
    _contrast_legend(ax)
    fig.text(0.075, 0.93, "When xOceania is allowed to act, the crash never happens.",
             color=WHITE, fontsize=24, fontweight="bold", ha="left", va="center")
    fig.savefig(STILLS_DIR / "still_4_hero.png", facecolor=BG_NAVY)
    paths.append(STILLS_DIR / "still_4_hero.png")
    plt.close(fig)

    return paths


def _annotate_too_late(ax, data: DemoData, alpha: float = 1.0) -> list:
    """Draw the trough annotation. Returns artist handles (for fading)."""
    sc = ax.scatter([data.trough_time], [data.trough_do], color=ORANGE, s=110,
                    zorder=7, alpha=alpha)
    ann = ax.annotate(
        "Farmer sees gasping fish at dawn, too late",
        xy=(data.trough_time, data.trough_do),
        xytext=(data.trough_time + 1.5, data.trough_do - 1.7),
        color=WHITE, fontsize=15, fontweight="bold", alpha=alpha,
        ha="left", va="top", zorder=8,
        arrowprops=dict(arrowstyle="->", color=ORANGE, lw=2.0, alpha=alpha),
        bbox=dict(boxstyle="round,pad=0.4", fc=PANEL, ec=ORANGE, lw=1.5, alpha=alpha),
    )
    return [sc, ann]


def _forecast_marker(ax, data: DemoData, alpha: float = 1.0) -> list:
    """Draw the 6h-ahead forecast marker. Returns artist handles (for fading)."""
    if data.forecast_time is None:
        return []
    vline = ax.axvline(data.forecast_time, color=BRIGHT, ls="-", lw=2.0,
                       alpha=0.85 * alpha)
    txt = ax.text(data.forecast_time - 0.5, 8.7,
                  "xOceania forecasts the crash 6h ahead",
                  color=BRIGHT, fontsize=14, fontweight="bold", ha="right",
                  va="top", alpha=alpha, zorder=8)
    return [vline, txt]


def _set_alpha(handles: list, alpha: float) -> None:
    """Set alpha on artist handles (scatter, text, line, annotation).

    For an Annotation the text alpha does not propagate to its bbox patch or
    arrow patch, so set those explicitly; otherwise the box and arrow never fade
    in during the animation.
    """
    for h in handles:
        try:
            h.set_alpha(alpha)
        except Exception:
            pass
        getter = getattr(h, "get_bbox_patch", None)
        if getter is not None:
            box = getter()
            if box is not None:
                box.set_alpha(alpha)
        arrow = getattr(h, "arrow_patch", None)
        if arrow is not None:
            arrow.set_alpha(alpha)


def _contrast_legend(ax) -> None:
    """Place the do-nothing vs acts legend in the empty lower-left of the panel."""
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return
    leg = ax.legend(handles, labels, loc="lower left", fontsize=16,
                    framealpha=0.0, handlelength=1.6, borderaxespad=1.2)
    for txt in leg.get_texts():
        txt.set_color(WHITE)
    leg.set_zorder(9)


# --- Animation -------------------------------------------------------------

def _build_story(data: DemoData, seconds: float = 36.0, fps: int = 20):
    """Build the figure and a frame `update(i)` callback for the full story.

    Returns (fig, update, total_frames). Duration is decoupled from curve
    resolution: `seconds` * `fps` frames are distributed across the story phases,
    and reveal progress maps onto the data. Artists are created exactly once and
    then updated, so nothing restacks. The same callback drives the MP4 (wrapped
    in FuncAnimation) and the streamed GIF.
    """
    b, x = data.do_nothing, data.xoceania
    tb, yb = _interp(b.t, b.DO)
    tx, yx = _interp(x.t, x.DO)
    n = len(tb)

    fig, ax = _base_figure()
    _night_shading(ax, DEMO_HOURS)
    _threshold(ax)

    (line_b,) = ax.plot([], [], color=DO_NOTHING_COLOR, lw=3.4, label="Do nothing")
    (line_x,) = ax.plot([], [], color=ACTS_COLOR, lw=3.8, label="xOceania acts")

    # Persistent artists, created once and faded/updated by the animator.
    danger = {"art": None}
    too_late = _annotate_too_late(ax, data, alpha=0.0)
    marker = _forecast_marker(ax, data, alpha=0.0)
    legend = {"done": False}

    total = int(round(seconds * fps))
    # Phase budget as fractions of the timeline (sum approx 1.0).
    fr = {"reveal_b": 0.40, "hold_1": 0.07, "annotate": 0.08,
          "forecast": 0.09, "reveal_x": 0.28, "hold_end": 0.08}
    bounds, acc = {}, 0.0
    for key in ("reveal_b", "hold_1", "annotate", "forecast", "reveal_x", "hold_end"):
        start = int(round(acc * total))
        acc += fr[key]
        end = int(round(acc * total))
        bounds[key] = (start, max(end, start + 1))
    bounds["hold_end"] = (bounds["hold_end"][0], total)

    def draw_danger(upto_idx: int) -> None:
        if danger["art"] is not None:
            danger["art"].remove()
        tt, yy = tb[:upto_idx], yb[:upto_idx]
        if len(tt) > 1:
            danger["art"] = ax.fill_between(
                tt, yy, STRESS_THRESHOLD, where=(yy < STRESS_THRESHOLD),
                color=ORANGE, alpha=0.28, lw=0, interpolate=True)

    def phase_progress(frame: int, key: str) -> float:
        s, e = bounds[key]
        if e <= s:
            return 1.0
        return min(1.0, max(0.0, (frame - s + 1) / (e - s)))

    def update(frame: int):
        # 1) Reveal the do-nothing curve and grow the danger fill underneath it.
        if frame < bounds["reveal_b"][1]:
            p = phase_progress(frame, "reveal_b")
            k = max(2, int(p * n))
            line_b.set_data(tb[:k], yb[:k])
            draw_danger(k)
            return ()
        # Past the reveal: full do-nothing curve and full danger zone.
        line_b.set_data(tb, yb)
        if danger["art"] is None or frame == bounds["reveal_b"][1]:
            draw_danger(n)

        # 2) Hold on the crash (nothing changes).
        # 3) Fade in the "too late" annotation.
        if frame >= bounds["annotate"][0]:
            a = phase_progress(frame, "annotate") if frame < bounds["annotate"][1] else 1.0
            _set_alpha(too_late, a)

        # 4) Fade in the 6h-ahead forecast marker.
        if frame >= bounds["forecast"][0]:
            a = phase_progress(frame, "forecast") if frame < bounds["forecast"][1] else 1.0
            _set_alpha(marker, a)

        # 5) Reveal the xOceania-acts curve; drop the contrast legend in.
        if frame >= bounds["reveal_x"][0]:
            p = phase_progress(frame, "reveal_x")
            k = max(2, int(p * n))
            line_x.set_data(tx[:k], yx[:k])
            if not legend["done"]:
                _contrast_legend(ax)
                legend["done"] = True
        return ()

    return fig, update, total


def build_animation(data: DemoData, seconds: float = 36.0, fps: int = 20):
    """Return (fig, FuncAnimation, n_frames) for the full story (used for MP4)."""
    from matplotlib.animation import FuncAnimation
    fig, update, total = _build_story(data, seconds=seconds, fps=fps)
    anim = FuncAnimation(fig, update, frames=total, interval=1000 / fps, blit=False)
    return fig, anim, total


def write_video(data: DemoData, seconds: float = 36.0, fps: int = 20) -> dict:
    """Write the MP4 (preferred) and a GIF fallback. Returns paths written."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    mp4_path = OUTPUT_DIR / "xoceania_demo.mp4"
    gif_path = OUTPUT_DIR / "xoceania_demo.gif"

    # Try MP4 via ffmpeg (imageio-ffmpeg provides the binary).
    try:
        import imageio_ffmpeg
        from matplotlib.animation import FFMpegWriter
        matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
        fig, anim, total = build_animation(data, seconds=seconds, fps=fps)
        writer = FFMpegWriter(fps=fps, bitrate=6000,
                              metadata=dict(title="xOceania pond DO demo"))
        anim.save(str(mp4_path), writer=writer, dpi=DPI,
                  savefig_kwargs={"facecolor": BG_NAVY})
        written["mp4"] = mp4_path
        plt.close(fig)
        print(f"[render]   mp4 frames: {total} at {fps} fps ({total / fps:.0f} s)")
    except Exception as exc:  # pragma: no cover - environment dependent
        print(f"[render] MP4 writer unavailable ({exc}); using GIF only.")

    # GIF fallback. Stream frames through imageio at reduced resolution instead
    # of buffering every full-res frame in memory (which is what makes Pillow GIF
    # writing crawl). We render at a coarser fps and lower dpi so the file stays
    # small and writes in well under a minute.
    try:
        import io
        import imageio.v2 as imageio

        gif_fps = 12
        gif_dpi = 48  # 19.2 in * 48 = 922 px wide
        fig2, update, total2 = _build_story(data, seconds=seconds, fps=gif_fps)
        with imageio.get_writer(str(gif_path), mode="I",
                                duration=1000.0 / gif_fps, loop=0) as writer:
            for i in range(total2):
                update(i)
                buf = io.BytesIO()
                fig2.savefig(buf, format="png", dpi=gif_dpi, facecolor=BG_NAVY)
                buf.seek(0)
                writer.append_data(imageio.imread(buf))
                buf.close()
        plt.close(fig2)
        written["gif"] = gif_path
        print(f"[render]   gif frames: {total2} at {gif_fps} fps (dpi {gif_dpi})")
    except Exception as exc:  # pragma: no cover
        print(f"[render] GIF writer failed: {exc}")

    return written


def main() -> None:
    print("[render] simulating both scenarios ...")
    data = compute_demo()
    print(f"[render]   do-nothing trough: {data.trough_do:.2f} mg/L at "
          f"{data.trough_time:.0f} h; xOceania min: {data.xoceania.DO.min():.2f} mg/L")
    print("[render] writing stills ...")
    stills = render_stills(data)
    for p in stills:
        print(f"[render]   {p}")
    print("[render] writing video ...")
    written = write_video(data)
    for kind, p in written.items():
        print(f"[render]   {kind}: {p}")
    print("[render] done.")


if __name__ == "__main__":
    main()
