import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import prototype as p


class PrototypeTest(unittest.TestCase):
    def setUp(self):
        p.DB.parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=p.DB.parent)
        self.addCleanup(self.temp.cleanup)
        self.db_patch = patch.object(p, "DB", Path(self.temp.name) / "demo.sqlite")
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        p.init()
        self.card = p.suggestions()[0]

    def event(self, action, **changes):
        body = dict(event_id=action + "-1", actor_id="demo-coordinator", role="coordinator",
                    reason="test", unit_id=self.card["unit_ids"][0],
                    unit_version=self.card["unit_version"],
                    destination=self.card["to_facility_id"])
        body.update(changes)
        if "actor_id" not in changes:
            body["actor_id"] = "demo-" + body["role"]
        return p.act(action, body)

    def test_approval_to_receipt_and_idempotency(self):
        first = self.event("accept")
        self.assertEqual(first, self.event("accept"))
        with self.assertRaises(p.ActionError) as ctx:
            self.event("accept", event_id="another")
        self.assertEqual(ctx.exception.status, 409)
        self.assertNotIn(self.card["unit_ids"][0], [s["unit_ids"][0] for s in p.suggestions()])
        move_id = first["move_id"]
        self.event("dispatch", role="sender", move_id=move_id, site=self.card["from_facility_id"])
        result = self.event("receive", role="receiver", move_id=move_id,
                            site=self.card["to_facility_id"], cold_chain_verified=False)
        self.assertEqual(result["safety"], "unknown")
        self.assertFalse(result["clinical_release"])

    def test_wrong_role_and_quarantine(self):
        with self.assertRaises(p.ActionError) as ctx:
            self.event("accept", role="sender")
        self.assertEqual(ctx.exception.status, 403)
        reserved = self.event("accept")
        self.event("quarantine", role="safety")
        with self.assertRaises(p.ActionError) as ctx:
            self.event("dispatch", role="sender", move_id=reserved["move_id"],
                       site=self.card["from_facility_id"])
        self.assertEqual(ctx.exception.status, 422)

    def test_fallback_is_computed(self):
        fallback = p.suggestions("fallback")
        self.assertTrue(fallback)
        self.assertTrue(all(s["fallback"] and s["eligibility_ok"] for s in fallback))

    def test_reject_removes_card_and_is_audited(self):
        self.event("reject")
        self.assertNotIn(self.card["unit_ids"][0],
                         [s["unit_ids"][0] for s in p.suggestions()])
        with p.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
