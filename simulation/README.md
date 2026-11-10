# simulation/

Run `uv run python -m simulation.compare` for a deliberately small one-shot comparison on synthetic 31 October closing stock, October request rates and 30 fresh Poisson demand seeds. Nearest and expiry-aware rankings share the same inventory, routes and demand draw per seed. The replay assumes every proposed transfer is accepted and arrives the next day, with no replenishment or courier capacity limit. It counts unmet requested units, expiries, moved units and origin-destination route batches separately. This is not a counterfactual replay of observed November events or a claim about actual blood-service outcomes.

Tier 2 scenario replay and policy comparison (expiry-aware vs nearest-site-first, and later variants). Seeded from the official closing snapshot and earlier request rates. Added future demand is synthetic, not observed November demand.

**Owner:** Blessings (`bleymambwe`).

**Status:** empty on purpose. Written in the official window.

Hold safety rules, initial stock, arrivals, demand, reserves, transport constraints and acceptance assumptions constant across policies. Report unmet units, expired units, moved units and route batches separately. Never claim lives or money saved.
