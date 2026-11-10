# Roles — equal team, no lead

Team Damu Grid has **no team lead and no manager title**. Blessings and Timi are taking the heavier tracks because they are the most available, not because they outrank Brayan or Dan. Everyone should be able to explain the whole workflow, the fallback, and what the measured result does not prove.

Official roster still has to match the check-in form. Showcase attendance (Nairobi / online) is **to confirm** for everyone.

| Teammate | GitHub | Location / time | Strengths used here | Ownership area |
|---|---|---|---|---|
| Agoro Oluwatimilehin Teslim (Timi) | `drizzy765` | Lagos, WAT (UTC+1, EAT−2) | Python, FastAPI, ML, LLM systems, evaluation, deployment | Backend API, workflow state machine, LLM explanation layer, deployment and integration |
| Blessings Mambwe | `bleymambwe` | Zambia (typically CAT, UTC+2, EAT−1; confirm) | Python ML evaluation and reproducibility (audits, benchmarks, Inspect AI, probing) | Forecasting, baseline evaluation harness and methodology, scenario simulator, reproducibility |
| Sorgho Brayan Jovani Aboubacar | `Sorghobrayan-dotcom` | Morocco, UIR Rabat (typically UTC+1; confirm) | Python, SQL, ML, financial data, LLM systems, optimisation prototype experience | Data pipeline / ETL and validation, SQLite schema, eligibility engine, cold-chain flags |
| Dan Boumba | `Dan-Boumba` | Kinshasa, DRC (typically WAT, UTC+1; confirm) | Web development, SaaS, TypeScript web apps, UX | Frontend review screen, map and dashboard, UX, demo video and slides design |

## Shared work (everyone)

Root README (official template), tests, demo rehearsal, check-ins, and submission. Dan assembles slides and records the video; everyone reviews the script and can narrate their part. Timi and Blessings still join README, testing and the demo — they are not excused from shared work because their tracks are heavier.

## Handoffs

- Brayan publishes a validated SQLite (or equivalent) and an eligibility function. Timi and Blessings consume it; they do not each invent a second schema.
- Blessings publishes the demand estimator, baseline metrics, and (Tier 2) simulator outputs as read-only artefacts. Timi's API reads them; it does not silently change the frozen evaluation.
- Timi publishes the suggestion and action API. Dan's UI is a client of that API, not a second source of truth for stock.
- Dan publishes click paths and the demo fixture list. Backend and data changes that break the demo path are coordinated in the channel before merge.

## Capacity

If a stream slips, cut inside that stream's Tier 2 first. Do not silently dump another person's must-ship work onto Timi or Blessings at 06:00. Pairing is encouraged.
