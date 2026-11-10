# tests/

Shared automated tests. Safety and state-machine tests are not optional.

**Owners:** everyone, in their area.

Planned:

- `pytest` for pipeline, eligibility, API actions (version conflicts, double reservation, quarantine cannot be cleared by the model), and the frozen evaluation arithmetic
- Playwright for the coordinator accept / change / reject / fallback click path

Bootstrap the exact commands in this file when packages exist. Until then, see `AGENTS.md`.
