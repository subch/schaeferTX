# Website Review — Clarity Pass (redesign/clarity-pass)

Audit and change log for the readability/usability/copy pass, August 2026.

## 1. Audit findings (before)

### Positioning
- **The site never said who it was for.** "Quality analytics & applied statistics"
  and "Turning laboratory data into decisions you can trust" could describe a
  hedge fund, a factory, or a lab. A lab director skimming on a phone had to
  infer the audience from demo names.
- **Deepest expertise was invisible.** LC-MS/MS urine toxicology — the strongest
  differentiator — appeared nowhere. HL7/Mirth experience was buried in one
  hero clause.
- **Services were vague.** Three generic cards ("Data Visualization", "Applied
  Statistics") with no deliverables, no page of their own, and no indication of
  what an engagement looks like or costs structure-wise.
- **Demos were presented as portfolio pieces, not proof.** "Projects" framing
  ("selected work", "a growing collection") read like a hobby portfolio rather
  than evidence of what a client would receive.

### Information architecture
- **Cluttered nav:** six items, three of which were individual demo links
  (Westgard Demo, Levey-Jennings Demo, HL7 Visualizer). On mobile this made a
  long menu where the three most important pages competed with three demos.
- **No services page, no clear next step** other than a bare contact page.
- **"Projects" naming** didn't match what the section actually was (live demos).

### Readability / accessibility
- `--text-faint` (#6b7890) measured ~4.3:1 on the page background and ~3.9:1 on
  card surfaces — below WCAG AA (4.5:1) — yet was used for real content:
  hero-stat labels, stat-tile labels, Westgard hints, rule descriptions.
- Several text sizes below 13px on content (tags 11.5px, rule descriptions
  12.5px, stat labels 12px).
- No `:focus-visible` styling — keyboard users got default (often invisible on
  dark) outlines.
- Mobile menu tap targets: the media query styled `nav.main-nav button`, but nav
  items are `<a>` elements, so the rule matched nothing; links were ~39px tall.
  Menu toggle was 40px (< 44px recommended).
- Body paragraphs had no max measure outside the hero; on wide screens prose ran
  the full 1120px container.

### Tests (pre-existing bug, found during this pass)
- **The vitest suite had been failing since it was introduced** (commit
  `13441ff`): three of four tests computed mean/SD from the same 5-point sample
  they were checking, so the outlier inflated the SD (e.g. sample
  `[100,101,99,100,300]` → SD ≈ 89) and no Westgard rule could ever fire.
  Nobody noticed because `.github/workflows/deploy.yml` only runs `npm ci` +
  `npm run build` — never `npm run test`.
- `npm run test` mapped to bare `vitest` (watch mode) — awkward for CI and
  one-shot local runs.

## 2. What changed and why

### Information architecture
- Nav reduced to **Home · Services · Demos · About · Contact (CTA)**. The three
  demo routes (`/westgard`, `/levey-jennings`, `/hl7`) remain as working deep
  links — reachable from Home and `/demos` — but left the nav.
- New **`/services`** page: six services, each with a 2–3 sentence description
  and a "typical deliverables" line, plus CTAs.
- **`/projects` renamed to `/demos`**, with `<Route path="/projects"
  element={<Navigate to="/demos" replace />} />` so existing links keep working
  (including deep loads via the GitHub Pages 404 redirect).
- Home restructured: hero → "Who I work with" strip → 3 service summary cards
  (linking to `/services`) → live demos → "Engagements in three steps"
  (scoping call → fixed-scope proposal → build & deliver) → final CTA band.

### Copy
- Hero now names the audience and the offer: "Custom software and QC expertise
  for clinical and toxicology labs," with the LC-MS/MS urine toxicology
  background stated up front. CTAs: "See the live demos" and "Book a scoping
  call" (mailto with pre-filled subject).
- Every demo card gained an evidence line tying it to hired work (e.g. "The
  same evaluation engine I build into private QC review tools for labs").
- Compliance service is phrased as **supporting the lab's compliance program**
  ("I work alongside your laboratory director"; "Your director retains
  oversight") — not acting as lab director.
- About rewritten around clinical/tox specialization and the bench-plus-code
  combination. **No facts were invented** — see TODO list below.
- Contact page sets expectations: what to include (lab type, instruments, LIS,
  problem statement) and a bracketed response-time placeholder.
- Header tagline: "Technical Scientific Consulting" → "Clinical & Toxicology
  Lab Consulting". Footer line updated to match.
- `index.html` / `public/404.html` titles, meta description, and OG tags updated
  to the new positioning.
- Hero stats kept truthful (3 live demos / 100% client-side / OSS), reworded
  slightly.

### Styles (polish, not re-theme — tokens and dark aesthetic kept)
- Global `p { max-width: 70ch; line-height: 1.65 }` for readable measure.
- `--text-muted` lightened `#9aa8bd → #a3b1c6`; `--text-faint` lightened
  `#6b7890 → #7f8ca2` (~5:1 on card surfaces) **and** removed from real content
  (hero stats, stat tiles, hints, rule descriptions now use `--text-muted`).
  Faint is now decorative/metadata only (footer, template column types).
- `:focus-visible` accent outline added globally.
- Mobile: nav link selector fixed (`a`, not `button`) with `min-height: 44px`;
  menu toggle bumped to 44px; hero lead sized down; `h2` uses `clamp()`.
- Small text bumped: tags 11.5→12px, rule descriptions 12.5→13px, stat labels
  12→12.5px. New components (audience strip, step cards, CTA band, service
  detail rows) built from existing tokens.

### Tests
- Rewrote `tests/westgard.test.js` to evaluate against a provided target
  mean/SD (`providedMean`/`providedSd`) — matching how QC limits are actually
  applied (lot targets, not statistics recomputed from the points under
  review). Added 4-1s and in-control (no false positives) cases; suite is now
  6 tests, all passing. `src/westgard.js` itself was not changed.
- `package.json`: `test` → `vitest run` (one-shot), new `test:watch` → `vitest`.
- Recommended follow-up: add `npm run test` to the deploy workflow so red tests
  block deploys.

### Verification note (sandbox)
This pass was authored in a sandbox whose network egress policy blocks
registry.npmjs.org (and npm CDN mirrors), so `npm install` / `vite build` /
`vitest` could not be executed there. Verification was done by: (a) esbuild
syntax check of every source file, (b) a full esbuild bundle of `src/main.jsx`
with npm deps external (module graph + JSX + CSS compile clean), and (c) running
the complete test suite under a minimal vitest-compatible node shim (6/6 pass).
**Run `npm install && npm run test && npm run build` locally before merging.**
No dependencies were changed, and the only routing change is additive
(`/services`, `/demos`, `/projects` redirect), so build risk is low.

## 3. TODO(Travis) — facts needed before/after launch

Nothing factual was invented. These placeholders need real, verified facts:

1. **About page** — `TODO(Travis)` in first paragraph: years of experience and
   role(s) in LC-MS/MS urine toxicology (e.g. "[X] years running confirmation
   testing as [role]").
2. **About page** — `TODO(Travis)` at end of bio: credentials, if applicable —
   degree(s), certifications (ASCP, NRCC, etc.), notable employers/lab
   settings. Publish only once confirmed accurate.
3. **Contact page** — `[1–2 business days]` response-time placeholder: confirm
   a realistic commitment.

Also review before launch (not placeholders, but judgment calls):
- The scoping call is described as free ("No charge, no obligation") — confirm
  that's the intended offer.
- Mailto CTAs use `tschaefer0@gmail.com` — consider a domain email
  (e.g. travis@schaefertx.com) for credibility.

## 4. Out of scope / future ideas

- Blog or case-study pages (best marketing asset once there are shareable
  client stories — anonymized case studies especially).
- Privacy-friendly analytics (Plausible/GoatCounter) to see which demos convert.
- Contact form with a backend (Formspree or similar) instead of mailto.
- OG image (`og:image`) for richer link previews.
- Per-route `<title>`/meta (react-helmet or a small effect) for SEO on
  /services and /demos.
- Testimonials/client logos once real ones exist (none fabricated now).
