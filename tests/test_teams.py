import json
import unittest

import test_core
from cyai.store import Store


class TeamTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        self.other = self.s.action("create_project", {"name": "Second projet", "root": str(self.fixture.root)})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def profile(self, name, role="member", connector="alpha", model="", prompt="", skills=None):
        return self.s.action("agent_profile_save", {"name": name, "role": role, "connector": connector, "model": model,
                                                    "prompt": prompt or ("Consignes de " + name), "skills": skills or ["analyse"]})["id"]

    def trio(self, project):
        ids = {"chief": self.profile("Chef", "chief"), "lead": self.profile("Lead", "lead", "beta", "beta-2"), "member": self.profile("Membre")}
        self.s.action("team_save", {"project_id": project})
        chief = self.s.action("team_add_member", {"project_id": project, "profile_id": ids["chief"], "role": "chief"})["id"]
        lead = self.s.action("team_add_member", {"project_id": project, "profile_id": ids["lead"], "role": "lead", "manager_id": chief})["id"]
        member = self.s.action("team_add_member", {"project_id": project, "profile_id": ids["member"], "role": "member", "manager_id": lead})["id"]
        return ids, chief, lead, member

    # --- library --------------------------------------------------------------------------

    def test_profiles_are_versioned_and_duplicates_are_independent(self):
        id = self.profile("Analyste", "lead", "alpha", "alpha-1", "Version un")
        first = self.s.action("agent_profile_get", {"id": id})
        self.assertEqual(first["revision"], 1)
        unchanged = self.s.action("agent_profile_save", {"id": id, "name": "Analyste", "role": "lead", "connector": "alpha",
                                                         "model": "alpha-1", "prompt": "Version un", "skills": ["analyse"]})
        self.assertTrue(unchanged["unchanged"])
        self.s.action("agent_profile_save", {"id": id, "name": "Analyste", "role": "lead", "connector": "alpha",
                                             "model": "alpha-1", "prompt": "Version deux", "skills": ["analyse"], "note": "Précision"})
        updated = self.s.action("agent_profile_get", {"id": id})
        self.assertEqual(updated["revision"], 2)
        self.assertEqual([r["revision"] for r in updated["revisions"]], [2, 1])
        self.assertEqual(updated["revisions"][1]["definition"]["prompt"], "Version un")
        copy = self.s.action("agent_profile_duplicate", {"id": id, "name": "Analyste bis"})
        self.assertNotEqual(copy["id"], id)
        self.assertEqual(self.s.action("agent_profile_get", {"id": copy["id"]})["revision"], 1)
        self.s.action("agent_profile_save", {"id": copy["id"], "name": "Analyste bis", "role": "lead", "connector": "alpha",
                                             "model": "alpha-1", "prompt": "Autre voie", "skills": ["analyse"]})
        self.assertEqual(self.s.action("agent_profile_get", {"id": id})["prompt"], "Version deux")

    def test_an_icon_is_saved_versioned_and_does_not_create_an_empty_revision(self):
        id = self.profile("Analyste", "lead")
        self.assertEqual(self.s.action("agent_profile_get", {"id": id})["icon"], "")
        # Saving the same definition again must not invent a revision just because the icon is empty.
        self.assertTrue(self.s.action("agent_profile_save", {"id": id, "name": "Analyste", "role": "lead", "connector": "alpha",
                                                             "prompt": "Consignes de Analyste", "skills": ["analyse"]}).get("unchanged"))
        self.s.action("agent_profile_save", {"id": id, "name": "Analyste", "role": "lead", "connector": "alpha", "icon": "🧭",
                                             "prompt": "Consignes de Analyste", "skills": ["analyse"]})
        profile = self.s.action("agent_profile_get", {"id": id})
        self.assertEqual((profile["icon"], profile["revision"]), ("🧭", 2))
        self.assertEqual(profile["revisions"][0]["definition"]["icon"], "🧭")
        self.assertEqual(profile["revisions"][1]["definition"].get("icon", ""), "")
        with self.assertRaises(ValueError):
            self.s.action("agent_profile_save", {"id": id, "name": "Analyste", "connector": "alpha", "icon": "beaucoup trop long"})

    def test_invalid_profile_fields_are_refused_with_an_explanation(self):
        with self.assertRaises(ValueError):
            self.s.action("agent_profile_save", {"name": "", "connector": "alpha"})
        with self.assertRaises(ValueError):
            self.s.action("agent_profile_save", {"name": "Sans connecteur", "connector": ""})
        with self.assertRaises(ValueError):
            self.s.action("agent_profile_save", {"name": "Rôle", "role": "patron", "connector": "alpha"})
        with self.assertRaises(ValueError):
            self.s.action("agent_profile_save", {"name": "Réglage", "connector": "alpha", "settings": {"temperature": "0.4"}})
        with self.assertRaises(ValueError):
            self.s.action("agent_profile_save", {"name": "Vitesse", "connector": "alpha", "settings": {"service_tier": "priority"}})

    def test_unknown_connector_and_model_stay_editable_and_are_reported(self):
        id = self.profile("Hors ligne", connector="inconnu", model="modele-x")
        profile = self.s.action("agent_profile_get", {"id": id})
        self.assertEqual(profile["status"]["connector"], "missing")
        self.assertEqual(profile["status"]["model"], "catalogue_indisponible")
        self.s.action("agent_profile_save", {"id": id, "name": "Hors ligne", "connector": "alpha", "model": "alpha-1", "prompt": "corrigé"})
        self.assertEqual(self.s.action("agent_profile_get", {"id": id})["status"]["connector"], "disabled")
        self.s.engine.connectors["alpha"].config["enabled"] = True
        self.s.catalogs["alpha"] = [{"id": "alpha-1"}]
        refreshed = self.s.action("agent_profile_get", {"id": id})
        self.assertEqual((refreshed["status"]["connector"], refreshed["status"]["model"]), ("enabled", "confirmed"))
        self.s.action("agent_profile_save", {"id": id, "name": "Hors ligne", "connector": "alpha", "model": "alpha-9", "prompt": "corrigé"})
        self.assertEqual(self.s.action("agent_profile_get", {"id": id})["status"]["model"], "unconfirmed")

    # --- team composition -----------------------------------------------------------------

    def test_hierarchy_is_saved_reread_and_declared_ready(self):
        ids, chief, lead, member = self.trio(self.p)
        team = self.s.action("team_get", {"project_id": self.p})
        self.assertEqual(team["issues"], [])
        self.assertEqual([m["manager_id"] for m in team["members"]], [None, chief, lead])
        self.assertEqual(self.s.action("team_save", {"project_id": self.p, "status": "ready"})["status"], "ready")
        # A new Store over the same file is what reopening the application does.
        reopened = Store(self.fixture.root / "db.sqlite3")
        try:
            rows = reopened.rows("SELECT * FROM team_members ORDER BY position")
            self.assertEqual([json.loads(r["definition"])["prompt"] for r in rows],
                             ["Consignes de Chef", "Consignes de Lead", "Consignes de Membre"])
            self.assertEqual(reopened.rows("SELECT status FROM teams")[0]["status"], "ready")
            self.assertEqual(len(reopened.rows("SELECT * FROM agent_profile_revisions")), 3)
        finally:
            reopened.close()

    def test_incomplete_team_is_saved_as_a_draft_with_explanations(self):
        self.s.action("team_save", {"project_id": self.p})
        orphan = self.s.action("team_add_member", {"project_id": self.p, "profile_id": self.profile("Isolé"), "role": "member"})["id"]
        team = self.s.action("team_get", {"project_id": self.p})
        codes = {i["code"] for i in team["issues"]}
        self.assertEqual(codes, {"no_chief", "missing_manager"})
        self.assertTrue(all(i["message"] for i in team["issues"]))
        self.assertEqual({i["member_id"] for i in team["issues"] if "member_id" in i}, {orphan})
        self.assertEqual(team["team"]["status"], "draft")
        with self.assertRaises(ValueError):
            self.s.action("team_save", {"project_id": self.p, "status": "ready"})
        self.assertEqual(self.s.action("team_get", {"project_id": self.p})["team"]["status"], "draft")

    def test_cycles_and_foreign_managers_are_refused_by_the_service(self):
        ids, chief, lead, member = self.trio(self.p)
        with self.assertRaises(ValueError):
            self.s.action("team_update_member", {"project_id": self.p, "id": chief, "role": "lead", "manager_id": lead})
        with self.assertRaises(ValueError):
            self.s.action("team_update_member", {"project_id": self.p, "id": lead, "manager_id": lead})
        with self.assertRaises(ValueError):
            self.s.action("team_update_member", {"project_id": self.p, "id": member, "manager_id": member})
        self.s.action("team_save", {"project_id": self.other})
        foreign = self.s.action("team_add_member", {"project_id": self.other, "profile_id": ids["chief"], "role": "chief"})["id"]
        with self.assertRaises(ValueError):
            self.s.action("team_update_member", {"project_id": self.p, "id": member, "manager_id": foreign})
        with self.assertRaises(ValueError):
            self.s.action("team_update_member", {"project_id": self.other, "id": member, "manager_id": foreign})
        with self.assertRaises(ValueError):
            self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["member"], "role": "member", "manager_id": foreign})
        # Only a chief or a lead may direct others.
        with self.assertRaises(ValueError):
            self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["member"], "role": "member", "manager_id": member})
        self.assertEqual(self.s.action("team_get", {"project_id": self.p})["issues"], [])

    def test_removing_a_manager_requires_a_reassignment_or_an_explicit_draft(self):
        ids, chief, lead, member = self.trio(self.p)
        with self.assertRaises(ValueError):
            self.s.action("team_remove_member", {"project_id": self.p, "id": lead})
        self.s.action("team_remove_member", {"project_id": self.p, "id": lead, "acknowledged": True})
        team = self.s.action("team_get", {"project_id": self.p})
        self.assertEqual([i["code"] for i in team["issues"]], ["missing_manager"])
        self.assertFalse([m for m in team["members"] if m["id"] == lead][0]["active"])
        second = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["lead"], "role": "lead", "manager_id": chief})["id"]
        self.s.action("team_update_member", {"project_id": self.p, "id": member, "manager_id": second})
        self.assertEqual(self.s.action("team_get", {"project_id": self.p})["issues"], [])
        self.s.action("team_remove_member", {"project_id": self.p, "id": second, "reassign_to": chief})
        team = self.s.action("team_get", {"project_id": self.p})
        self.assertEqual(team["issues"], [])
        self.assertEqual([m for m in team["members"] if m["id"] == member][0]["manager_id"], chief)

    def test_projects_do_not_share_assignments_when_reusing_the_same_profiles(self):
        ids, chief, lead, member = self.trio(self.p)
        self.s.action("team_save", {"project_id": self.other})
        other_chief = self.s.action("team_add_member", {"project_id": self.other, "profile_id": ids["chief"], "role": "chief",
                                                        "responsibility": "Périmètre du second projet"})["id"]
        self.s.action("team_update_member", {"project_id": self.p, "id": chief, "responsibility": "Périmètre du premier projet"})
        first = self.s.action("team_get", {"project_id": self.p})
        second = self.s.action("team_get", {"project_id": self.other})
        self.assertTrue({m["id"] for m in first["members"]}.isdisjoint({m["id"] for m in second["members"]}))
        self.assertEqual(len(second["members"]), 1)
        self.assertEqual([m for m in first["members"] if m["id"] == chief][0]["responsibility"], "Périmètre du premier projet")
        self.assertEqual([m for m in second["members"] if m["id"] == other_chief][0]["responsibility"], "Périmètre du second projet")

    def test_global_edits_never_change_existing_teams_until_adopted(self):
        ids, chief, lead, member = self.trio(self.p)
        self.s.action("team_save", {"project_id": self.other})
        other_lead = self.s.action("team_add_member", {"project_id": self.other, "profile_id": ids["lead"], "role": "chief"})["id"]
        self.s.action("agent_profile_save", {"id": ids["lead"], "name": "Lead", "role": "lead", "connector": "beta",
                                             "model": "beta-2", "prompt": "Consignes révisées", "skills": ["analyse"]})
        frozen = [m for m in self.s.action("team_get", {"project_id": self.p})["members"] if m["id"] == lead][0]
        self.assertEqual(frozen["definition"]["prompt"], "Consignes de Lead")
        self.assertEqual((frozen["profile_revision"], frozen["profile_revision_current"], frozen["update_available"]), (1, 2, True))
        preview = self.s.action("team_revision_preview", {"project_id": self.p, "id": lead})
        self.assertEqual([c["field"] for c in preview["changes"]], ["prompt"])
        self.assertEqual([m for m in self.s.action("team_get", {"project_id": self.p})["members"] if m["id"] == lead][0]["definition"]["prompt"],
                         "Consignes de Lead")
        self.s.action("team_adopt_revision", {"project_id": self.p, "id": lead})
        self.assertEqual([m for m in self.s.action("team_get", {"project_id": self.p})["members"] if m["id"] == lead][0]["definition"]["prompt"],
                         "Consignes révisées")
        untouched = [m for m in self.s.action("team_get", {"project_id": self.other})["members"] if m["id"] == other_lead][0]
        self.assertEqual((untouched["profile_revision"], untouched["definition"]["prompt"]), (1, "Consignes de Lead"))

    def test_archiving_a_profile_keeps_teams_and_revision_history(self):
        ids, chief, lead, member = self.trio(self.p)
        self.s.action("agent_profile_archive", {"id": ids["lead"]})
        team = self.s.action("team_get", {"project_id": self.p})
        self.assertEqual(team["issues"], [])
        self.assertTrue([m for m in team["members"] if m["id"] == lead][0]["profile_archived"])
        self.assertEqual([m for m in team["members"] if m["id"] == lead][0]["definition"]["prompt"], "Consignes de Lead")
        self.assertEqual(len(self.s.action("agent_profile_get", {"id": ids["lead"]})["revisions"]), 1)
        with self.assertRaises(ValueError):
            self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["lead"], "role": "lead", "manager_id": chief})
        self.s.action("agent_profile_archive", {"id": ids["lead"], "archived": False})
        self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["lead"], "role": "lead", "manager_id": chief})
        self.assertEqual(len(self.s.action("team_get", {"project_id": self.p})["members"]), 4)

    def test_connector_problems_never_block_configuration_nor_fake_readiness(self):
        ids, chief, lead, member = self.trio(self.p)
        team = self.s.action("team_get", {"project_id": self.p})
        self.assertTrue(team["warnings"])
        self.assertEqual(team["issues"], [])
        self.assertTrue(all(w["code"].startswith(("connector_", "model_")) for w in team["warnings"]))
        self.s.action("team_save", {"project_id": self.p, "status": "ready"})
        ready = self.s.action("team_get", {"project_id": self.p})
        self.assertTrue(ready["ready"])
        self.assertTrue(ready["warnings"], "les avertissements d’exécution restent visibles sur une équipe prête")
        self.s.action("team_update_member", {"project_id": self.p, "id": member, "responsibility": "Toujours modifiable"})

    def test_a_consultant_sits_outside_the_chain_of_command(self):
        ids, chief, lead, member = self.trio(self.p)
        expert = self.profile("Chercheur web", "consultant", "beta")
        consultant = self.s.action("team_add_member", {"project_id": self.p, "profile_id": expert, "role": "consultant",
                                                       "responsibility": "Recherche documentaire à la demande"})["id"]
        team = self.s.action("team_get", {"project_id": self.p})
        self.assertEqual(team["issues"], [], "un consultant sans responsable n’est pas un problème de composition")
        self.s.action("team_save", {"project_id": self.p, "status": "ready"})
        card = [m for m in team["members"] if m["id"] == consultant][0]
        self.assertEqual((card["role"], card["manager_id"]), ("consultant", None))
        self.assertEqual(card["role_label"], "Consultant · sollicité à la tâche")
        # It directs nobody, and an optional referent stays possible.
        with self.assertRaises(ValueError):
            self.s.action("team_update_member", {"project_id": self.p, "id": member, "manager_id": consultant})
        self.s.action("team_update_member", {"project_id": self.p, "id": consultant, "manager_id": lead})
        self.assertEqual(self.s.action("team_get", {"project_id": self.p})["issues"], [])
        # Retiring the referent reassigns the consultant like any other attachment, and the team stays valid.
        self.s.action("team_remove_member", {"project_id": self.p, "id": lead, "reassign_to": chief})
        team = self.s.action("team_get", {"project_id": self.p})
        self.assertEqual(team["issues"], [])
        self.assertEqual([m for m in team["members"] if m["id"] == consultant][0]["manager_id"], chief)
        # Dropping the referent altogether leaves a consultant perfectly valid.
        self.s.action("team_update_member", {"project_id": self.p, "id": consultant, "manager_id": ""})
        self.assertEqual(self.s.action("team_get", {"project_id": self.p})["issues"], [])

    def test_everything_is_editable_on_an_assignment_without_touching_the_profile(self):
        ids, chief, lead, member = self.trio(self.p)
        self.s.action("team_save", {"project_id": self.other})
        twin = self.s.action("team_add_member", {"project_id": self.other, "profile_id": ids["member"], "role": "chief"})["id"]
        result = self.s.action("team_update_member", {"project_id": self.p, "id": member, "overrides": {
            "name": "Membre · variante rapide", "icon": "⚡", "model": "alpha-9", "connector": "alpha",
            "prompt": "Consignes retouchées pour ce projet.", "skills": ["python", "sqlite"],
            "description": "Variante locale.", "settings": {"effort": "high"}}})
        self.assertIn("appartiennent à cette affectation", result["notice"])
        card = [m for m in self.s.action("team_get", {"project_id": self.p})["members"] if m["id"] == member][0]
        self.assertEqual(card["definition"]["name"], "Membre · variante rapide")
        self.assertEqual((card["definition"]["model"], card["definition"]["icon"]), ("alpha-9", "⚡"))
        self.assertEqual(card["definition"]["settings"], {"effort": "high"})
        self.assertEqual(card["frozen"]["name"], "Membre", "la révision figée est intacte")
        self.assertEqual(sorted(card["overridden"]), ["description", "icon", "model", "name", "prompt", "settings", "skills"])
        self.assertIn("Modèle", card["override_labels"])
        # Neither the global profile nor the other project moved.
        self.assertEqual(self.s.action("agent_profile_get", {"id": ids["member"]})["revision"], 1)
        self.assertEqual(self.s.action("agent_profile_get", {"id": ids["member"]})["name"], "Membre")
        elsewhere = [m for m in self.s.action("team_get", {"project_id": self.other})["members"] if m["id"] == twin][0]
        self.assertEqual(elsewhere["definition"]["name"], "Membre")
        self.assertEqual(elsewhere["overridden"], [])

    def test_a_local_edit_survives_a_revision_and_can_be_cleared(self):
        ids, chief, lead, member = self.trio(self.p)
        self.s.action("team_update_member", {"project_id": self.p, "id": member, "overrides": {"model": "alpha-local"}})
        self.s.action("agent_profile_save", {"id": ids["member"], "name": "Membre", "role": "member", "connector": "alpha",
                                             "model": "alpha-officiel", "prompt": "Consignes de Membre", "skills": ["analyse"]})
        preview = self.s.action("team_revision_preview", {"project_id": self.p, "id": member})
        self.assertIn("Modèle", preview["overridden"])
        self.assertIn("resteront prioritaires", preview["notice"])
        self.s.action("team_adopt_revision", {"project_id": self.p, "id": member})
        card = [m for m in self.s.action("team_get", {"project_id": self.p})["members"] if m["id"] == member][0]
        self.assertEqual(card["definition"]["model"], "alpha-local", "la surcharge locale reste prioritaire")
        self.assertEqual(card["frozen"]["model"], "alpha-officiel")
        cleared = self.s.action("team_update_member", {"project_id": self.p, "id": member, "overrides": {}})
        self.assertIn("Retour à la définition figée", cleared["notice"])
        card = [m for m in self.s.action("team_get", {"project_id": self.p})["members"] if m["id"] == member][0]
        self.assertEqual((card["definition"]["model"], card["overridden"]), ("alpha-officiel", []))

    def test_local_edits_are_validated_like_a_profile_and_follow_the_template(self):
        ids, chief, lead, member = self.trio(self.p)
        with self.assertRaises(ValueError) as refusal:
            self.s.action("team_update_member", {"project_id": self.p, "id": member, "overrides": {"role": "chief"}})
        self.assertIn("non modifiable localement", str(refusal.exception))
        with self.assertRaises(ValueError):
            self.s.action("team_update_member", {"project_id": self.p, "id": member, "overrides": {"name": "  "}})
        with self.assertRaises(ValueError):
            self.s.action("team_update_member", {"project_id": self.p, "id": member, "overrides": {"settings": {"service_tier": "fast"}}})
        with self.assertRaises(ValueError):
            self.s.action("team_update_member", {"project_id": self.p, "id": member, "overrides": {"connector": ""}})
        self.s.action("team_update_member", {"project_id": self.p, "id": member, "overrides": {"model": "alpha-local", "icon": "🧪"}})
        self.s.action("team_save_template", {"project_id": self.p, "name": "Avec surcharges"})
        template = self.s.action("team_template_list", {})["templates"][0]
        self.s.action("team_apply_template", {"project_id": self.other, "template_id": template["id"]})
        applied = [m for m in self.s.action("team_get", {"project_id": self.other})["members"] if m["role"] == "member"][0]
        self.assertEqual(applied["definition"]["model"], "alpha-local")
        self.assertEqual(applied["frozen"]["model"], "", "le modèle du profil reste celui de la révision")
        self.assertEqual(applied["overridden"], ["icon", "model"])

    # --- templates ------------------------------------------------------------------------

    def test_template_rebuilds_the_hierarchy_with_new_assignments(self):
        ids, chief, lead, member = self.trio(self.p)
        self.s.action("team_update_member", {"project_id": self.p, "id": member, "responsibility": "Tests"})
        self.s.action("team_save_template", {"project_id": self.p, "name": "Trio standard"})
        template = self.s.action("team_template_list", {})["templates"][0]
        self.assertEqual(len(template["composition"]["members"]), 3)
        conversation = self.s.action("create_conversation", {"project_id": self.p, "title": "Discussion source"})["id"]
        self.s.action("save_memory", {"project_id": self.p, "content": "Mémoire du projet source"})
        self.s.action("team_apply_template", {"project_id": self.other, "template_id": template["id"]})
        applied = self.s.action("team_get", {"project_id": self.other})
        self.assertEqual(applied["issues"], [])
        self.assertTrue({m["id"] for m in applied["members"]}.isdisjoint({chief, lead, member}))
        by_role = {m["role"]: m for m in applied["members"]}
        self.assertIsNone(by_role["chief"]["manager_id"])
        self.assertEqual(by_role["lead"]["manager_id"], by_role["chief"]["id"])
        self.assertEqual(by_role["member"]["manager_id"], by_role["lead"]["id"])
        self.assertEqual(by_role["member"]["responsibility"], "Tests")
        self.assertFalse(self.s.store.rows("SELECT id FROM conversations WHERE project_id=?", (self.other,)))
        self.assertFalse(self.s.memory(self.other))
        self.assertTrue(self.s.store.rows("SELECT id FROM conversations WHERE id=?", (conversation,)))
        with self.assertRaises(ValueError):
            self.s.action("team_apply_template", {"project_id": self.other, "template_id": template["id"]})
        self.s.action("team_apply_template", {"project_id": self.other, "template_id": template["id"], "replace": True})
        self.assertEqual(len(self.s.action("team_get", {"project_id": self.other})["members"]), 3)
        self.s.action("team_template_delete", {"id": template["id"]})
        self.assertEqual(self.s.action("team_template_list", {})["templates"], [])
        self.assertEqual(len(self.s.action("team_get", {"project_id": self.other})["members"]), 3)

    # --- persistence and migration --------------------------------------------------------

    def test_backup_carries_the_library_and_older_backups_stay_restorable(self):
        ids, chief, lead, member = self.trio(self.p)
        backup = self.s.action("backup", {})
        self.assertEqual(backup["version"], 2)
        self.assertEqual(len(backup["tables"]["team_members"]), 3)
        from cyai.service import TEAM_TABLES
        legacy = {**backup, "version": 1, "tables": {k: v for k, v in backup["tables"].items() if k not in set(TEAM_TABLES)}}
        result = self.s.action("restore", {"backup": legacy, "acknowledged": True})
        self.assertIn("bibliothèque d’agents globale", result["notice"])
        self.assertEqual(len(self.s.action("agent_profile_list", {})["profiles"]), 3)
        self.assertEqual(self.s.action("team_get", {"project_id": self.p})["team"], None)
        self.s.action("restore", {"backup": backup, "acknowledged": True})
        restored = self.s.action("team_get", {"project_id": self.p})
        self.assertEqual(len(restored["members"]), 3)
        self.assertEqual(restored["issues"], [])

    def test_schema_arrives_on_a_database_created_before_this_lot(self):
        """A pre-lot-1 database gains the tables and keeps its conversations and memory."""
        import sqlite3
        legacy = self.fixture.root / "ancienne.sqlite3"
        db = sqlite3.connect(legacy)
        try:
            db.executescript("""
                CREATE TABLE projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, root TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE conversations(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                  title TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0, parent_id TEXT, branch_message_id TEXT, created_at TEXT NOT NULL);
                CREATE TABLE messages(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, role TEXT NOT NULL, connector TEXT,
                  provider TEXT, model TEXT, content TEXT NOT NULL, created_at TEXT NOT NULL, source_id TEXT);
                CREATE TABLE sessions(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                  connector TEXT NOT NULL, model TEXT NOT NULL, native_id TEXT, last_seq INTEGER DEFAULT 0, created_at TEXT NOT NULL);
                CREATE TABLE memory(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                  content TEXT NOT NULL, validated INTEGER NOT NULL DEFAULT 0, source_ids TEXT NOT NULL, created_at TEXT NOT NULL);
                INSERT INTO projects VALUES('p1','Projet ancien','C:\\\\ancien','2026-01-01T00:00:00.000+00:00');
                INSERT INTO conversations VALUES('c1','p1','Ancienne conversation',0,NULL,NULL,'2026-01-01T00:00:00.000+00:00');
                INSERT INTO messages(id,conversation_id,role,content,created_at) VALUES('m1','c1','user','Message à conserver','2026-01-01T00:00:00.000+00:00');
                INSERT INTO memory VALUES('mem1','p1','Mémoire à conserver',1,'[]','2026-01-01T00:00:00.000+00:00');
            """)
            db.commit()
        finally:
            db.close()
        migrated = Store(legacy)
        try:
            tables = {r["name"] for r in migrated.rows("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({"agent_profiles", "agent_profile_revisions", "teams", "team_members", "team_templates"}.issubset(tables))
            self.assertEqual(migrated.rows("SELECT content FROM messages")[0]["content"], "Message à conserver")
            self.assertEqual(migrated.rows("SELECT content FROM memory")[0]["content"], "Mémoire à conserver")
            self.assertEqual(migrated.rows("SELECT title FROM conversations")[0]["title"], "Ancienne conversation")
            self.assertEqual(migrated.rows("SELECT COUNT(*) AS n FROM agent_profiles")[0]["n"], 0)
        finally:
            migrated.close()


if __name__ == "__main__":
    unittest.main()
