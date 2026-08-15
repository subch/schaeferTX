# Updates — Westgard rules

This branch implements the full Westgard multi-rule evaluator and improves the demo UI.

What's included:
- src/westgard.js: more complete evaluator (1_2s, 1_3s, 2_2s, R4s, 4_1s, 10_x), robust median+MAD option, and API to pass provided mean/SD.
- src/components/WestgardDemo.jsx: column selector, rule toggles, example loader, export annotated CSV.
- examples/: a few synthetic CSVs demonstrating common failure modes (Na spikes, K drift, cholesterol 10-in-a-row).
- tests/: basic unit tests using Vitest to demonstrate the evaluator behavior.
- docs/westgard-paper-notes.md: placeholder notes linking to PMC9300779 and suggested discussion points (I can't fetch the paper here; tell me if you'd like me to fetch and summarize it exactly).

To run tests locally:
- npm install
- npm run test

