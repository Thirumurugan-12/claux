# Datathon 2026 — Submission Deck

`KSP_Crime_Intelligence_Submission.pptx` — the completed KSP Datathon 2026 prototype
submission, built on the official Hack2Skill template and filled from this project.

Regenerate from the template with:

```
python build_deck.py    # expects ppt/template.pptx alongside (the official template)
```

## Before submitting — fill these in

- **Slide 1** — Team name, Team leader name, Team size.
- **Slide 13** — Demo video link (3 min) and the deployed Catalyst URL.

Everything else (brief, USP, features, process flow, architecture, technologies, Catalyst
services, cost, snapshots, benchmarks, roadmap) is complete with real project data.

Metrics on the benchmarking slide are measured, not estimated: entity-resolution B³ F1 0.687,
MO clustering homogeneity 1.000 / V-measure 0.681, 40/40 orchestration eval, 158 tests.

> Note: the deck was assembled with `python-pptx` (LibreOffice rendering was unavailable in
> the build environment), and QA'd via schema validation + a geometry/text-fit audit. Open it
> once in PowerPoint to eyeball spacing. Slide 11's UI screens are vector mockups — swap in
> live screenshots once the app is running against the Catalyst LLM endpoint.
