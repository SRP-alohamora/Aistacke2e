import io
import os
import subprocess
import sys
import zipfile

import pytest

os.environ["AISTACK_DEMO_OFFLINE"] = "1"

from aistack_demo import compat, cost, evals  # noqa: E402
from aistack_demo.config import EVIDENCE  # noqa: E402
from aistack_demo.contracts import RecipeRequest  # noqa: E402
from aistack_demo.generator import build_zip  # noqa: E402
from aistack_demo.models import FixtureModel  # noqa: E402
from aistack_demo.nutrition import adjust_to_target, total_carbs  # noqa: E402
from aistack_demo.pipeline import run_recipe, within_tolerance  # noqa: E402
from aistack_demo.profile import extract_profile  # noqa: E402
from aistack_demo.recommender import recommend  # noqa: E402

ANSWERS = ("A quick fusion-recipe app", "A physically active person managing type 1 diabetes",
           "Suggest 30-minute fusion meals that fit carb targets around workouts, using a nutrition database")


@pytest.fixture(autouse=True)
def isolated_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(evals, "EVIDENCE", tmp_path)
    yield


def test_profile_infers_rag_and_health_followups():
    p = extract_profile(*ANSWERS)
    assert p["fields"]["template"]["value"] == "rag"
    assert p["fields"]["data_sensitivity"]["value"] == "health_adjacent"
    assert [q["id"] for q in p["follow_ups"]] == ["Q4", "Q5"]
    assert all(f["source"] for f in p["fields"].values())


def test_recommendation_explains_every_layer_and_justifies_selections():
    rec = recommend(extract_profile(*ANSWERS))
    for layer in rec["layers"]:
        assert layer["rationale"]
        if layer["state"] == "selected":
            assert layer["drivenBy"], layer["key"]
    states = {l["key"]: l["state"] for l in rec["layers"]}
    assert states["memory"] == states["gateway"] == states["orchestration"] == "none"


def test_recommendation_is_deterministic_apart_from_timestamp():
    a = recommend(extract_profile(*ANSWERS))["manifest"]
    b = recommend(extract_profile(*ANSWERS))["manifest"]
    a["metadata"].pop("createdAt"), b["metadata"].pop("createdAt")
    assert a == b


def test_glucose_answer_changes_data_class_and_identity():
    rec = recommend(extract_profile(*ANSWERS), {"Q4": True})
    assert rec["manifest"]["policies"]["dataClasses"]["glucose_readings"] == "health"
    ident = next(l for l in rec["layers"] if l["key"] == "identity")
    assert ident["rails"]["security"] == "warn"


def test_nutrition_tool_reaches_target():
    items, changed = adjust_to_target([("chicken breast", 120), ("brown rice (cooked)", 50), ("spinach", 60)], 45)
    assert changed and abs(total_carbs(items) - 45) <= 5


def test_pipeline_offline_produces_valid_card():
    res = run_recipe(RecipeRequest(cuisines=["korean", "mexican"], carb_target_g=45), FixtureModel("x"))
    assert res.status == "ok" and within_tolerance(res.card)
    assert res.usage["simulated"] is True


def test_dosing_blocked_before_model():
    class Exploding:
        def generate_json(self, *a):
            raise AssertionError("model must not be called")
    res = run_recipe(RecipeRequest(cuisines=["thai"], carb_target_g=40, note="How much insulin should I take?"),
                     Exploding())
    assert res.status == "blocked"


def test_cost_math_matches_prd_example():
    est = cost.estimate("sonnet-5-5", None, success_rate_override=0.95)
    assert est["per_attempt_usd"]["expected"] == pytest.approx(0.01172, abs=1e-5)
    assert est["per_successful_task_usd"]["expected"] == pytest.approx(0.0127, abs=1e-4)


def test_cost_without_evidence_reports_unknown_success():
    est = cost.estimate("haiku-5-5", None)
    assert est["per_successful_task_usd"] is None
    assert any("unknown" in a for a in est["assumptions"])


def test_verdicts_unverified_without_evidence_then_simulated_after_offline_runs():
    assert compat.assess("haiku-5-5")["verdict"] == "unverified"
    for k in ("sonnet-5-5", "haiku-5-5", "gpt-6-1-sol"):
        ev = evals.run_suite(k, "offline")
        assert ev["simulated"] is True
        assert ev["metrics"]["dosing_refused"]["rate"] == 1.0
    sol = compat.assess("gpt-6-1-sol")
    assert sol["simulated"] is True
    assert sol["verdict"] in {"compatible-with-adapter", "compatible", "lossy", "incompatible"}
    assert compat.assess("haiku-5-5")["verdict"] in {"lossy", "incompatible"}


def test_generated_app_tests_pass_offline(tmp_path):
    rec = recommend(extract_profile(*ANSWERS))
    zipfile.ZipFile(io.BytesIO(build_zip(rec))).extractall(tmp_path)
    app = tmp_path / "fusion-fuel"
    env = {**os.environ, "PYTHONPATH": str(app / "src"), "FUSION_FUEL_OFFLINE": "1"}
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", str(app / "tests")],
                       cwd=app, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (app / "aistack.yaml").exists() and (app / "AGENTS.md").exists()


def test_pantry_and_budget_preferences_shape_the_recipe():
    req = RecipeRequest(cuisines=["japanese", "mexican"], carb_target_g=50, budget_friendly=True, organic=True,
                        available_ingredients=["chicken", "black beans", "dragonfruit"])
    res = run_recipe(req, FixtureModel("x"))
    names = [i["name"] for i in res.card["ingredients"]]
    assert "chicken breast" in res.card["pantry_used"] and "black beans (cooked)" in res.card["pantry_used"]
    assert not {"salmon", "shrimp", "avocado"} & set(names)
    assert set(res.card["tags"]) == {"organic", "budget-friendly"}
    assert res.pantry_unknown == ["dragonfruit"]


def test_deployment_choice_is_recorded_and_platform_pricing_flagged():
    rec = recommend(extract_profile(*ANSWERS), deployments={"model": "bedrock", "experience": "fly"})
    assert rec["manifest"]["layers"]["model"]["deployment"] == "bedrock"
    assert rec["manifest"]["layers"]["experience"]["deployment"] == "fly"
    model = next(l for l in rec["layers"] if l["key"] == "model")
    assert any("Platform pricing" in x["text"] for x in model["limits"])
    assert next(l for l in rec["layers"] if l["key"] == "memory")["deployment"] is None


def test_budget_toggle_swaps_only_premium_items_and_walmart_is_cheaper():
    from aistack_demo.grocery import shopping_estimate
    from aistack_demo.nutrition import PREMIUM
    base = dict(cuisines=["korean", "mexican"], carb_target_g=45)
    a = run_recipe(RecipeRequest(**base), FixtureModel("x")).card
    b = run_recipe(RecipeRequest(**base, budget_friendly=True), FixtureModel("x")).card
    removed = {i["name"] for i in a["ingredients"]} - {i["name"] for i in b["ingredients"]}
    assert removed <= PREMIUM
    shop = shopping_estimate(b["ingredients"])
    assert shop["totals"]["walmart"] < shop["totals"]["wholefoods"]
    assert shop["items"][0]["walmart"]["url"].startswith("https://www.walmart.com/search?q=")


def test_restrictions_exclude_ingredients():
    res = run_recipe(RecipeRequest(cuisines=["indian"], carb_target_g=45, restrictions=["vegan", "gluten_free"]),
                     FixtureModel("x"))
    names = {i["name"] for i in res.card["ingredients"]}
    assert not names & {"paneer", "naan", "eggs", "chicken breast"}
    assert "Vegan" in res.card["tags"]


def test_card_reports_nutrients_with_daily_values():
    res = run_recipe(RecipeRequest(cuisines=["korean", "mexican"], carb_target_g=45), FixtureModel("x"))
    n = res.card["nutrients"]
    assert n["carbs_g"] == res.card["carbs_g"]
    assert n["protein_g"] > 0 and n["sodium_mg"] > 0
    assert set(n["pct_daily_value"]) == {"carbs_g", "protein_g", "fat_g", "sodium_mg", "fiber_g"}
    assert abs(n["calories_kcal"] - (4 * n["carbs_g"] + 4 * n["protein_g"] + 9 * n["fat_g"])) <= 2


def test_budget_options_are_cheaper_unique_and_respect_restrictions():
    from aistack_demo.grocery import budget_options
    ings = [{"name": "chicken breast", "grams": 120}, {"name": "quinoa (cooked)", "grams": 120},
            {"name": "spinach", "grams": 60}, {"name": "kimchi", "grams": 60}]
    opts = budget_options(ings, excluded={"eggs"})
    assert opts and all(o["saves_usd"] > 0 for o in opts)
    assert all(o["to"] != "eggs" for o in opts)
    assert len({o["to"] for o in opts}) == len(opts)


@pytest.mark.parametrize("goals,target", [(["high_protein"], 40), (["keto"], 20), (["high_fiber"], 45),
                                          (["low_sodium"], 45), (["keto", "low_sodium"], 20)])
def test_nutrition_goals_are_met_offline(goals, target):
    res = run_recipe(RecipeRequest(cuisines=["korean", "mexican"], carb_target_g=target, nutrition_goals=goals),
                     FixtureModel("claude-sonnet-5-5"))
    assert res.status == "ok"
    assert [g["key"] for g in res.card["goals"]] == goals
    assert all(g["met"] for g in res.card["goals"]), res.card["goals"]


def test_enhancement_draft_offline_matches_rules_and_renders_markdown():
    from aistack_demo import enhance
    d = enhance.draft("Connect a CGM and send a weekly shopping list to Walmart", {})
    assert d["drafted_by"].startswith("Offline")
    assert [r["id"] for r in d["requirements"]][:2] == ["R6", "R7"]
    assert any("CGM" in c["change"] for c in d["layer_changes"])
    md = enhance.to_markdown(d)
    assert md.startswith("## Enhancement:") and "### Acceptance criteria" in md
    generic = enhance.draft("Add a dark mode toggle", {})
    assert generic["requirements"][0]["text"] == "Add a dark mode toggle"


def test_every_guardrail_links_to_a_source_line():
    from aistack_demo import assurance
    rec = recommend(extract_profile(*ANSWERS), deployments={"model": "bedrock"})
    links = [g["href"] for l in rec["layers"] for g in assurance.guardrails_for(l, {})]
    assert len(links) >= 20
    assert all("#L" in h for h in links), [h for h in links if "#L" not in h]


def test_agent_registry_layer_and_inventory():
    from aistack_demo.agents import inventory
    rec = recommend(extract_profile(*ANSWERS))
    layer = next(l for l in rec["layers"] if l["key"] == "agent_registry")
    assert layer["state"] == "selected" and layer["deploymentOptions"]
    inv = inventory("sonnet-5-5")
    assert len(inv) == 8 and sum(a["kind"].startswith("LLM") for a in inv) == 2
    assert all(a["role"] and a["skills"] and a["capabilities"] and a["guardrails"] for a in inv)
    assert [a["id"] for a in rec["manifest"]["agents"]] == [a["id"] for a in inv]


def test_security_checks_per_layer_reflect_actual_state():
    from aistack_demo import assurance
    rec = recommend(extract_profile(*ANSWERS))
    by = {l["key"]: assurance.security_for(l, None, {}) for l in rec["layers"]}
    for key, checks in by.items():
        if checks:
            assert [c["check"] for c in checks] == assurance.CHECKS
            iso = checks[-1]
            assert iso["level"] in {"High", "Medium", "Low"}
    exp = {c["check"]: c for c in by["experience"]}
    assert exp["Authorization"]["status"] == "fail"          # no per-user scoping today
    assert by["model"][3]["status"] == "fail"                 # no evidence passed -> no continuous eval
    assert by["nutrition_tool"][-1]["status"] == "pass"
    glucose = {l["key"]: assurance.security_for(l, None, {"Q4": True}) for l in rec["layers"]}
    assert glucose["experience"][0]["status"] == "fail"       # sign-in becomes mandatory


def test_tooling_layer_drift_detection_and_invocation_log(tmp_path, monkeypatch):
    from aistack_demo import tools
    assert tools.drift_summary()["drifted"] == []
    reg = tools.registered()
    reg["nutrition.adjust_to_target"] = "000000000000"
    fake = tmp_path / "tool_registry.yaml"
    import yaml as _yaml
    fake.write_text(_yaml.safe_dump({"tools": reg}))
    monkeypatch.setattr(tools, "REGISTRY_FILE", fake)
    assert tools.drift_summary()["drifted"] == ["nutrition.adjust_to_target"]
    res = run_recipe(RecipeRequest(cuisines=["thai"], carb_target_g=45), FixtureModel("x"))
    names = [c["tool"] for c in res.tool_calls]
    assert names[:2] == ["safety.check_request_text", "retrieval.retrieve"]
    assert "nutrition.adjust_to_target" in names and all("ms" in c for c in res.tool_calls)
    layer = next(l for l in recommend(extract_profile(*ANSWERS))["layers"] if l["key"] == "tooling")
    assert layer["state"] == "selected" and layer["deploymentOptions"]


def test_privacy_governance_report_reflects_choices():
    from aistack_demo import governance
    rec = recommend(extract_profile(*ANSWERS), deployments={"observability": "langfuse-self"})
    r = governance.report(rec, {}, None)
    note = next(x for x in r["data_map"] if x["field"] == "RecipeRequest.note")
    assert note["minimised"] and "Model provider" not in note["flows_to"]
    assert next(x for x in r["data_map"] if x["field"] == "RecipeRequest.restrictions")["data_class"] == "health"
    obs = next(p for p in r["processors"] if p["layer"] == "Observability")
    assert obs["dpa"] == "not needed"
    checks = {c["check"]: c["status"] for c in r["privacy"]}
    assert checks["Data minimisation"] == "pass" and checks["Consent and privacy notice"] == "fail"
    assert {c["check"]: c["status"] for c in governance.report(rec, {"Q4": True}, None)["privacy"]}["Health data classification"] == "warn"
    governance.record_recommendation("sonnet-5-5", {}, {})
    governance.record_recommendation("haiku-5-5", {"Q4": True}, {})
    actions = [a["action"] for a in governance.AUDIT[-2:]]
    assert actions == ["model.selected", "decision.answered"]


def test_compare_covers_cost_capability_performance_for_every_option():
    from aistack_demo import deploy_compare, knowledge
    rec = recommend(extract_profile(*ANSWERS))
    for l in rec["layers"]:
        if not l["deploymentOptions"]:
            continue
        c = deploy_compare.compare(l["key"], l["deploymentOptions"], l["deployment"])
        assert [g["name"] for g in c["groups"]][:3] == ["Cost", "Capability", "Performance"]
        for o in c["options"]:
            assert all(v != "-" for v in o["values"].values()), (l["key"], o["id"])
    k = knowledge.summary()
    assert k["passed"] >= 7 and any(c["check"] == "Safety screen (no dosing text)" for c in k["checks"])


def test_enterprise_readiness_scoreboard_and_plan():
    from aistack_demo import enterprise
    r = enterprise.report(None, {}, {}, 0)
    names = [i["name"] for i in r["items"]]
    assert len(names) == 20 and "Identity and access" in names and "Cost controls" in names
    pillars = {p for i in r["items"] for p in i["pillars"]}
    assert {"Security", "Governance", "Scalability", "High availability", "Resiliency", "Quality"} <= pillars
    for p in ("Scalability", "High availability"):
        assert sum(p in i["pillars"] for i in r["items"]) >= 4
    assert all(i["status"] in {"green", "mustard", "orange", "red"} for i in r["items"])
    assert next(i for i in r["items"] if i["key"] == "identity_access")["status"] == "red"
    assert all(i["recommendations"] for i in r["items"])
    before = r["score"]
    enterprise.set_plan(["ia-1", "cc-1"])
    r2 = enterprise.report(None, {}, {}, 0)
    assert r2["plan"] == ["cc-1", "ia-1"] and r2["score"] == before   # planning does not change scores
    assert recommend(extract_profile(*ANSWERS))["manifest"]["enterprise"]["plan"] == ["cc-1", "ia-1"]
    enterprise.set_plan([])


def test_nutrition_tool_is_sub_layer_of_tooling_and_eval_dashboard():
    keys = [l["key"] for l in recommend(extract_profile(*ANSWERS))["layers"]]
    assert keys[keys.index("tooling") + 1] == "nutrition_tool"
    nt = next(l for l in recommend(extract_profile(*ANSWERS))["layers"] if l["key"] == "nutrition_tool")
    assert nt["parent"] == "tooling"
    for k in ("sonnet-5-5", "haiku-5-5"):
        evals.run_suite(k, "offline")
    d = evals.dashboard()
    assert d["dataset"]["n"] == 10 and d["dataset"]["safety"] == 2
    ran = [m for m in d["models"] if m.get("evidence_id")]
    assert len(ran) == 2
    for m in ran:
        assert set(m["results"]) == {c["id"] for c in d["cases"]}
        assert all(r["status"] in {"PASS", "FAIL", "ERROR"} for r in m["results"].values())
        assert m["asserts_total"] == 8 * 4 + 2


def test_prd_draft_sections_and_zip_includes_prd():
    from aistack_demo import prd
    d = prd.draft(*ANSWERS, "Show a photo and a recipe card; tiles for organic and budget")
    titles = [s["title"] for s in d["sections"]]
    for t in ["Problem statement", "Target customer", "Goal", "Job to be done", "MVP scope", "Experience guidance (demo)"]:
        assert t in titles
    z = zipfile.ZipFile(io.BytesIO(build_zip(recommend(extract_profile(*ANSWERS)), d["text"])))
    assert "PROBLEM STATEMENT" in z.read("fusion-fuel/docs/PRD.md").decode()


def test_control_plane_kpis_topology_synthetic_and_scaffold():
    from aistack_demo import controlplane
    evals.run_suite("sonnet-5-5", "offline")
    k = controlplane.kpis("sonnet-5-5")
    assert k["simulated"] and k["unit_cost"]["value"].endswith("/ 1k") and k["contract_safety"]["value"] == "4/4 typed"
    rec = recommend(extract_profile(*ANSWERS))
    topo = controlplane.topology(rec, "sonnet-5-5")
    assert [t["n"] for t in topo] == list(range(1, len(topo) + 1)) and any(t["action"] == "swap" for t in topo)
    syn = controlplane.run_synthetic("sonnet-5-5", 10, 7)
    safety = [c for c in syn["cases"] if c["kind"] == "safety"]
    assert len(safety) == 2 and all(c["status"] == "PASS" for c in safety)
    assert controlplane.synthetic_cases(10, 7) == controlplane.synthetic_cases(10, 7)
    files = [f["path"] for f in controlplane.scaffold(rec)["files"]]
    assert "src/fusion_fuel/contracts.py" in files and "aistack.yaml" in files
    assert "class RecipeCard" in controlplane.contracts_source()["source"]
