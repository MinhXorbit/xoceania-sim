# Lovable prompt — xOceania hero / landing page

Paste everything in the fenced block below into Lovable. It builds the marketing
hero (landing page). The interactive operator demo and the live pond are a separate
app I built (in `app/`); the landing page's main call-to-action links to that demo.

Before pasting, replace `DEMO_URL_HERE` with wherever the demo is hosted (the
Netlify/Vercel/Lovable URL of the `app/` site).

---

```
Build a single-page marketing landing site for "xOceania", a digital twin for
aquaculture shrimp ponds. Mobile-first, fast, no backend. Stack: React + Vite +
Tailwind + shadcn/ui. It must look like a premium, calm, scientific climate-tech
product, not a generic SaaS template.

THE STORY (use this voice and these facts):
xOceania is a digital twin for intensive shrimp ponds in the Mekong Delta
(Penaeus vannamei). A pond looks fine all day. Overnight, dissolved oxygen quietly
falls and crashes below the lethal line just before dawn, and the shrimp suffocate.
The farmer only finds out at sunrise, after the loss. xOceania runs a process-based
model of the pond, forecasts the crash about 6 hours ahead, and drives aeration the
moment the forecast nears the stress line, so the crash never happens.

BRAND (use these exact colors, dark theme only):
- Background navy #071726, panel #0E2336, deeper chrome #0A1E30, hairline border #14304a
- Primary accent teal #2BC4D4, bright highlight #5EEAD4
- Danger / loss orange #F0734A, warning amber #FFC14D
- Text #E8F2F5, muted #A6BBC8, dim #7C97A6
- Clean sans-serif (Inter or system). Two weights: regular and semibold. Sentence
  case everywhere, never ALL CAPS, never title case. No em dashes in any copy; use
  commas, colons or hyphens. Flat surfaces, subtle 1px borders, generous spacing.
  Very subtle gradients on the hero background are fine; no neon, no heavy shadows.

LAYOUT (sections, top to bottom):
1. Sticky slim top bar: small logo circle + wordmark "xOceania" on the left, and a
   primary button "See it live" on the right that links to DEMO_URL_HERE.
2. Hero: a small teal eyebrow "Aquaculture digital twin". A large headline where the
   first line is white and the second line is in the orange accent:
   "A pond looks fine all day."  /  "Overnight, the oxygen crashes."
   A muted sub-paragraph (the story above, 2 sentences). Two buttons: primary teal
   "See it live" (links to DEMO_URL_HERE) and a ghost "Watch the 30s film" (anchor
   to the film section). To the side / below on mobile, show a simple decorative
   line-chart illustration of dissolved oxygen over a night: a teal line that dips
   below a dashed amber "5 mg/L stress" line into a faint orange shaded zone near
   dawn. Keep it lightweight (inline SVG), it is illustrative, not interactive.
3. Problem band ("The silent killer"): three short stats in cards, e.g.
   "Pre-dawn", "DO 2.3 mg/L at the trough", "6 h of warning". Keep numbers bold in
   teal, labels muted.
4. Solution: heading "Sense, forecast, act." Three cards in a row (stack on mobile),
   each with a Tabler-style icon, a title and one muted sentence:
   - Sense: probes stream oxygen, pH, temperature, ammonia and salinity.
   - Forecast: a coupled-ODE twin predicts the overnight crash hours ahead.
   - Act: it drives aeration before the forecast hits the stress line.
5. Film section (id="film"): a heading "The 30-second story" and a 16:9 video
   placeholder (poster image, play button) the user can later point at the demo film.
6. Big call-to-action band: navy panel, headline "See the crash before it happens",
   one muted line, and a large primary teal button "Open the live demo" linking to
   DEMO_URL_HERE. Make this the visual climax.
7. Footer: "xOceania", a line "Paper 1 simulator is open-source on GitHub" with a
   link, and a small dim note "Concept demo. Numbers are illustrative."

REQUIREMENTS:
- Mobile-first and fully responsive; looks great at 390px wide (this will be opened
  from a QR code on phones).
- Accessible: semantic headings, alt text, good contrast, focus states.
- No backend, no auth, no database. Static content only.
- Fast: no heavy libraries beyond the stack. Smooth, subtle scroll-reveal animations
  are welcome but keep them tasteful.
- Every "See it live" / "Open the live demo" button links to DEMO_URL_HERE and opens
  in the same tab.
- Use a placeholder logo (a teal circle with a small wave mark) if no asset is
  uploaded; I will replace it with the real xOceania logo.
```

---

## Notes for you (not for Lovable)

- This prompt produces the landing page only. The real interactive demo (operator
  dashboard + the live animated pond) is the `app/` site in this repo. Host that
  first, then drop its URL into `DEMO_URL_HERE` so the landing CTA points at it.
- Upload the real logo (`app/assets/logo.png`) and the film poster
  (`app/assets/poster.png`) into Lovable to replace the placeholders.
- If you later want the landing page and the demo to live in one Lovable project,
  tell me and I will port the demo (operator view + pond) into React so it drops
  straight into the Lovable codebase.
