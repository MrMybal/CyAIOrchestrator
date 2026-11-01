import json
import time
import unittest

import test_core
from cyai import specialists


class HelperTests(unittest.TestCase):
    """A specialist called as a tool, while another agent is working."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config = {**connector.config, "enabled": True}
        self.imager = self.s.action("agent_profile_save", {
            "name": "Fabricant d’images", "role": "consultant", "connector": "beta",
            "prompt": "Tu produis des images de référence."})["id"]
        self.modeller = self.s.action("agent_profile_save", {
            "name": "Modeleur", "role": "member", "connector": "alpha", "prompt": "Tu modélises dans Blender.",
            "helpers": [{"profile_id": self.imager, "purpose": "produire les images de référence"}]})["id"]
        self.conversation = self.s.action("create_conversation", {"project_id": self.p, "title": "Chaîne"})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def run_with_tool(self, calls):
        """Let the fixture agent use the specialist tool exactly as a real CLI would."""
        seen = {"answers": [], "tools": []}

        def run(prompt, root, model, native_id, control):
            control.emit("session", {"native_id": "n"})
            token = control.mcp_servers["cyai_plugins"]["env"]["CYAI_PLUGIN_TOKEN"]
            seen["tools"] = [t["name"] for t in self.s.plugins.gateway(token, {"method": "tools/list"})["tools"]]
            for request in calls:
                seen["answers"].append(self.s.plugins.gateway(
                    token, {"method": "tools/call", "params": {"name": "cyai_specialist", "arguments": request}}))
            return "modelage terminé"

        self.s.engine.connectors["alpha"].run = run
        mission = self.s.action("create_mission", {"conversation_id": self.conversation, "title": "Modelage",
                                                   "steps": [{"profile_id": self.modeller, "instruction": "Modélise un vaisseau."}]})["mission_id"]
        self.s.engine.launch(mission)
        deadline = time.time() + 20
        while time.time() < deadline and self.s.store.one("SELECT status FROM missions WHERE id=?", (mission,))["status"] in (
                "queued", "running", "awaiting_approval", "pausing"):
            time.sleep(.05)
        return seen, self.s.mission(mission)

    def answers(self, seen):
        return [json.loads(a["content"][0]["text"]) if not a.get("isError") else a["content"][0]["text"] for a in seen["answers"]]

    # --- the tool exists only where it was declared -------------------------------------------

    def test_the_tool_appears_only_for_an_agent_that_declares_specialists(self):
        seen, mission = self.run_with_tool([])
        self.assertIn("cyai_specialist", seen["tools"])
        self.assertEqual(mission["status"], "succeeded")
        # An agent without declared helpers does not see the tool at all.
        plain = self.s.action("agent_profile_save", {"name": "Seul", "role": "member", "connector": "alpha"})["id"]
        self.modeller = plain
        seen, mission = self.run_with_tool([])
        self.assertNotIn("cyai_specialist", seen["tools"])

    def test_a_specialist_answers_and_its_call_is_recorded_in_the_chain(self):
        seen, mission = self.run_with_tool([{"specialist": "Fabricant d’images", "request": "Trois vues de référence."}])
        answer = self.answers(seen)[0]
        self.assertEqual(answer["specialist"], "Fabricant d’images")
        self.assertEqual(answer["answer"], "beta résultat vérifiable")
        self.assertEqual((answer["call"], answer["remaining"]), (1, specialists.MAX_CALLS - 1))
        self.assertIn("CyAI ne l’a pas vérifiée", answer["notice"])
        kinds = [e["kind"] for e in mission["events"]]
        self.assertIn("specialist_requested", kinds)
        self.assertIn("specialist_answered", kinds)
        requested = next(e for e in mission["events"] if e["kind"] == "specialist_requested")["data"]
        self.assertEqual((requested["specialist"], requested["connector"]), ("Fabricant d’images", "beta"))
        self.assertIn("Trois vues de référence.", requested["request"])
        self.assertIn("pas une preuve", requested["notice"])
        # The helper received its own instructions, and was told not to take over the task.
        prompt = self.s.engine.connectors["beta"].calls[0][0]
        self.assertIn("Tu produis des images de référence.", prompt)
        self.assertIn("sans prendre en charge le reste de sa tâche", prompt)

    def test_a_specialist_cannot_call_specialists_of_its_own(self):
        nested = []

        def imaging(prompt, root, model, native_id, control):
            nested.append(dict(getattr(control, "mcp_servers", {})))
            return "image produite"

        self.s.engine.connectors["beta"].run = imaging
        self.run_with_tool([{"specialist": "Fabricant d’images", "request": "Une image."}])
        self.assertEqual(nested, [{}], "le spécialiste n’a aucun MCP, donc aucun spécialiste à appeler")

    # --- guardrails ---------------------------------------------------------------------------

    def test_the_number_of_calls_is_capped_and_said_plainly(self):
        request = {"specialist": "Fabricant d’images", "request": "Encore une image."}
        seen, mission = self.run_with_tool([request] * (specialists.MAX_CALLS + 2))
        answers = self.answers(seen)
        self.assertEqual(len([a for a in answers if isinstance(a, dict)]), specialists.MAX_CALLS)
        refusals = [a for a in answers if isinstance(a, str)]
        self.assertEqual(len(refusals), 2)
        self.assertIn("Plafond de " + str(specialists.MAX_CALLS), refusals[0])
        self.assertIn("plutôt que de continuer à demander", refusals[0])
        self.assertEqual(len(self.s.engine.connectors["beta"].calls), specialists.MAX_CALLS)
        self.assertEqual(mission["status"], "succeeded", "le plafond n’échoue pas l’étape, il la borne")

    def test_an_unknown_or_unavailable_specialist_is_refused_with_what_to_do(self):
        seen, mission = self.run_with_tool([
            {"specialist": "Inconnu", "request": "Fais"},
            {"specialist": "Fabricant d’images", "request": "   "}])
        refusals = self.answers(seen)
        self.assertIn("Spécialiste inconnu", refusals[0])
        self.assertIn("Fabricant d’images", refusals[0])
        self.assertIn("Décrivez ce que vous demandez", refusals[1])
        self.s.action("agent_profile_archive", {"id": self.imager})
        seen, mission = self.run_with_tool([{"specialist": "Fabricant d’images", "request": "Une image."}])
        self.assertIn("indisponible", self.answers(seen)[0])
        self.assertIn("Faites sans lui", self.answers(seen)[0])

    def test_a_failing_specialist_is_reported_without_stopping_the_caller(self):
        self.s.engine.connectors["beta"].mode = "fail"
        seen, mission = self.run_with_tool([{"specialist": "Fabricant d’images", "request": "Une image."}])
        self.assertIn("a échoué", self.answers(seen)[0])
        self.assertIn("Poursuivez sans lui", self.answers(seen)[0])
        self.assertEqual(mission["status"], "succeeded", "l’échec du spécialiste n’échoue pas l’appelant")
        self.assertIn("specialist_failed", [e["kind"] for e in mission["events"]])

    # --- declaration rules --------------------------------------------------------------------

    def test_declared_specialists_are_versioned_validated_and_overridable(self):
        profile = self.s.action("agent_profile_get", {"id": self.modeller})
        self.assertEqual(profile["helpers"], [{"profile_id": self.imager, "purpose": "produire les images de référence"}])
        self.assertEqual(profile["revisions"][0]["definition"]["helpers"][0]["profile_id"], self.imager)
        with self.assertRaises(ValueError) as refusal:
            self.s.action("agent_profile_save", {"id": self.modeller, "name": "Modeleur", "connector": "alpha",
                                                 "helpers": [{"profile_id": self.modeller}]})
        self.assertIn("lui-même", str(refusal.exception))
        with self.assertRaises(ValueError):
            self.s.action("agent_profile_save", {"id": self.modeller, "name": "Modeleur", "connector": "alpha",
                                                 "helpers": [{"profile_id": "fantome"}]})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("agent_profile_save", {"id": self.modeller, "name": "Modeleur", "connector": "alpha",
                                                 "helpers": [{"profile_id": self.imager, "purpose": str(i)} for i in range(specialists.MAX_HELPERS + 1)]})
        self.assertIn("écrivez une méthode", str(refusal.exception))
        # An assignment may change the list locally, like any other field.
        self.s.action("team_save", {"project_id": self.p})
        member = self.s.action("team_add_member", {"project_id": self.p, "profile_id": self.modeller, "role": "chief"})["id"]
        self.s.action("team_update_member", {"project_id": self.p, "id": member, "overrides": {"helpers": []}})
        card = [m for m in self.s.action("team_get", {"project_id": self.p})["members"] if m["id"] == member][0]
        self.assertEqual(card["definition"]["helpers"], [])
        self.assertEqual(card["frozen"]["helpers"][0]["profile_id"], self.imager)
        self.assertIn("Spécialistes appelables", card["override_labels"])


if __name__ == "__main__":
    unittest.main()
