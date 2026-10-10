"""FastAPI app: the demo API plus a single-page UI."""
from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
import html

from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from . import prd as prd_mod
from . import controlplane
from . import agents, assurance, compat, cost, deploy_compare, enterprise, evals, governance, knowledge, tools
from .config import DATA, STATIC, forced_offline, mode_for, prices
from .contracts import RecipeRequest
from .generator import ADVANCED_DIAGRAM, BEGINNER_DIAGRAM, build_zip
from . import enhance
from .grocery import budget_options, shopping_estimate
from .photos import choose_photo
from .pipeline import all_exclusions, run_recipe
from .restrictions import RESTRICTIONS
from .profile import extract_profile
from .recommender import recommend
from .config import make_model

app = FastAPI(title="AiStackE2E demo-opus.001")
LAST_TOOL_CALLS: list[dict] = []
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class Answers(BaseModel):
    build: str
    user: str
    goal: str
    guidance: str = ""


class RecommendIn(BaseModel):
    answers: Answers
    follow_ups: dict[str, bool] = {}
    model_key: str | None = None
    deployments: dict[str, str] = {}
    prd_text: str = ""


class EnhanceIn(RecommendIn):
    text: str


class RunIn(BaseModel):
    model_key: str
    request: dict


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status() -> dict:
    p = prices()
    return {"forced_offline": forced_offline(),
            "models": {k: {"label": v["label"], "provider": v["provider"], "model_id": v["model_id"],
                           "mode": mode_for(k), "has_evidence": evals.load_evidence(k) is not None}
                       for k, v in p["models"].items()},
            "baseline": p["baseline"], "catalog_version": p["catalog_version"]}


@app.post("/api/profile")
def profile(a: Answers) -> dict:
    return extract_profile(a.build, a.user, a.goal, a.guidance)


@app.post("/api/prd")
def prd(a: Answers) -> dict:
    return prd_mod.draft(a.build, a.user, a.goal, a.guidance)


@app.post("/api/recommend")
def do_recommend(body: RecommendIn) -> dict:
    prof = extract_profile(body.answers.build, body.answers.user, body.answers.goal, body.answers.guidance)
    key = body.model_key or prices()["baseline"]
    if key not in prices()["models"]:
        raise HTTPException(422, f"unknown model_key {key}")
    rec = recommend(prof, body.follow_ups, key, body.deployments)
    rec["profile"] = prof
    rec["diagrams"] = {"beginner": BEGINNER_DIAGRAM,
                       "advanced": ADVANCED_DIAGRAM.format(model=prices()["models"][key]["label"])}
    ev = evals.load_evidence(key)
    governance.record_recommendation(key, body.follow_ups, body.deployments)
    rec["cost"] = cost.estimate(key, ev)
    # Guardrails are shown as a column per layer, not as their own row.
    rec["layers"] = [l for l in rec["layers"] if l["key"] != "guardrails"]
    for l in rec["layers"]:
        l["quality"] = assurance.quality_for(l, ev)
        l["guardrails"] = assurance.guardrails_for(l, body.follow_ups)
        l["security"] = assurance.security_for(l, ev, body.follow_ups)
        l["compare"] = deploy_compare.compare(l["key"], l.get("deploymentOptions", []), l.get("deployment")) \
            if l.get("deploymentOptions") else None
        p = prices()
        l["provenance"] = governance.provenance_for(l, key, p["baseline"], body.deployments, body.follow_ups, ev,
                                                    p["catalog_version"], p["models"][key]["source"])
    rec["agents"] = agents.inventory(key)
    rec["knowledge"] = knowledge.summary()
    rec["tools"] = {"inventory": tools.inventory(), "mcp_servers": tools.MCP_SERVERS,
                    "mcp_candidates": tools.MCP_CANDIDATES, "last_calls": LAST_TOOL_CALLS}
    return rec


@app.get("/api/models/compare")
def compare() -> dict:
    out = []
    for key in prices()["models"]:
        ev = evals.load_evidence(key)
        out.append({"model_key": key, "mode": mode_for(key), "cost": cost.estimate(key, ev),
                    "compat": compat.assess(key),
                    "evidence": None if not ev else {k: ev[k] for k in (
                        "evidence_id", "simulated", "mode", "metrics", "success", "latency_ms",
                        "created_at", "expires_at", "mapping_losses")}})
    return {"baseline": prices()["baseline"], "models": out}


@app.get("/api/evals/dashboard")
def evals_dashboard() -> dict:
    return evals.dashboard()


@app.post("/api/evals/all")
def run_all_evals() -> dict:
    out = {}
    for key in prices()["models"]:
        ev = evals.run_suite(key)
        governance.audit("eval.run", f"{key}: {ev['success']['passed']}/{ev['success']['total']} "
                         f"({'simulated' if ev['simulated'] else 'measured'})")
        out[key] = ev["success"]
    return out


@app.post("/api/evals/{model_key}")
def run_eval(model_key: str, offline: bool = False) -> dict:
    if model_key not in prices()["models"]:
        raise HTTPException(404, "unknown model")
    ev = evals.run_suite(model_key, "offline" if offline else None)
    governance.audit("eval.run", f"{model_key}: {ev['success']['passed']}/{ev['success']['total']} "
                     f"({'simulated' if ev['simulated'] else 'measured'})")
    return {k: v for k, v in ev.items() if k != "cases"}


@app.post("/api/generate")
def generate(body: RecommendIn) -> Response:
    prof = extract_profile(body.answers.build, body.answers.user, body.answers.goal, body.answers.guidance)
    rec = recommend(prof, body.follow_ups, body.model_key or prices()["baseline"], body.deployments)
    governance.audit("app.generated", f"fusion-fuel.zip with {rec['manifest']['layers']['model']['component']}")
    return Response(build_zip(rec, body.prd_text), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="fusion-fuel.zip"'})


@app.post("/api/run")
def live_run(body: RunIn) -> dict:
    if body.model_key not in prices()["models"]:
        raise HTTPException(404, "unknown model")
    try:
        req = RecipeRequest(**body.request)
    except ValidationError as e:
        raise HTTPException(422, json.loads(e.json()))
    res = run_recipe(req, make_model(body.model_key))
    out = {"mode": mode_for(body.model_key), **res.to_dict()}
    if res.card:
        names = [i["name"] for i in res.card["ingredients"]]
        log = tools.ToolLog()
        with log.call("photos.choose_photo", ingredients=len(names), cuisines=req.cuisines):
            out["photo"] = choose_photo(names, req.cuisines)
        with log.call("grocery.shopping_estimate", ingredients=len(names)):
            out["shopping"] = shopping_estimate(res.card["ingredients"])
        with log.call("grocery.budget_options", ingredients=len(names), excluded=len(all_exclusions(req))):
            opts = budget_options(res.card["ingredients"], set(all_exclusions(req)))
        out["tool_calls"] = out["tool_calls"] + log.calls
        out["shopping"]["budget_options"] = opts
        out["shopping"]["totals"]["walmart_with_options"] = round(
            out["shopping"]["totals"]["walmart"] - sum(o["saves_usd"] for o in opts), 2)
    LAST_TOOL_CALLS[:] = out["tool_calls"]
    return out


@app.post("/api/governance")
def privacy_governance(body: RecommendIn) -> dict:
    prof = extract_profile(body.answers.build, body.answers.user, body.answers.goal, body.answers.guidance)
    key = body.model_key or prices()["baseline"]
    rec = recommend(prof, body.follow_ups, key, body.deployments)
    return governance.report(rec, body.follow_ups, evals.load_evidence(key))


@app.post("/api/enterprise")
def enterprise_report(body: RecommendIn) -> dict:
    key = body.model_key or prices()["baseline"]
    return enterprise.report(evals.load_evidence(key), body.follow_ups, body.deployments, len(governance.AUDIT))


class PlanIn(BaseModel):
    ids: list[str]


@app.post("/api/enterprise/plan")
def enterprise_plan(body: PlanIn) -> dict:
    before = set(enterprise.PLAN)
    plan = enterprise.set_plan(body.ids)
    added, removed = sorted(set(plan) - before), sorted(before - set(plan))
    if added or removed:
        governance.audit("enterprise.plan", f"enabled {', '.join(added) or '-'}; removed {', '.join(removed) or '-'}")
    return {"plan": plan}


@app.post("/api/control-plane")
def control_plane(body: RecommendIn) -> dict:
    key = body.model_key or prices()["baseline"]
    prof = extract_profile(body.answers.build, body.answers.user, body.answers.goal, body.answers.guidance)
    rec = recommend(prof, body.follow_ups, key, body.deployments)
    return {"kpis": controlplane.kpis(key), "topology": controlplane.topology(rec, key),
            "model_label": prices()["models"][key]["label"]}


@app.get("/api/contracts")
def contracts_view() -> dict:
    return controlplane.contracts_source()


class SyntheticIn(BaseModel):
    model_key: str
    n: int = 10
    seed: int = 7


@app.post("/api/synthetic")
def synthetic(body: SyntheticIn) -> dict:
    if body.model_key not in prices()["models"]:
        raise HTTPException(404, "unknown model")
    out = controlplane.run_synthetic(body.model_key, max(1, min(body.n, 30)), body.seed)
    governance.audit("synthetic.run", f"{body.model_key}: {out['passed']}/{out['total']} (seed {body.seed}, {out['mode']})")
    return out


@app.post("/api/scaffold")
def scaffold(body: RecommendIn) -> dict:
    prof = extract_profile(body.answers.build, body.answers.user, body.answers.goal, body.answers.guidance)
    rec = recommend(prof, body.follow_ups, body.model_key or prices()["baseline"], body.deployments)
    return controlplane.scaffold(rec, body.prd_text)


@app.post("/api/enhancements")
def enhancements(body: EnhanceIn) -> dict:
    if not body.text.strip():
        raise HTTPException(422, "describe the enhancement first")
    prof = extract_profile(body.answers.build, body.answers.user, body.answers.goal, body.answers.guidance)
    rec = recommend(prof, body.follow_ups, body.model_key or prices()["baseline"], body.deployments)
    d = enhance.draft(body.text[:2000], rec["manifest"])
    governance.audit("enhancement.drafted", f"{d['title'][:60]} ({d['drafted_by']})")
    return {**d, "markdown": enhance.to_markdown(d)}


@app.get("/source/{name}", response_class=HTMLResponse)
def source(name: str) -> str:
    """Read-only view of a whitelisted demo source file, with line anchors for guardrail links."""
    path = assurance.SOURCE_FILES.get(name)
    if not path:
        raise HTTPException(404, "not a demo source file")
    rows = "".join(f'<tr id="L{i}"><td class="n"><a href="#L{i}">{i}</a></td><td><pre>{html.escape(line)}</pre></td></tr>'
                   for i, line in enumerate(path.read_text().splitlines(), 1))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(name)}</title>
<style>body{{margin:0;font:13px/1.5 ui-monospace,Menlo,monospace;background:#fff;color:#202124}}
header{{padding:12px 20px;border-bottom:1px solid #dadce0;font:500 15px Roboto,system-ui,sans-serif;position:sticky;top:0;background:#fff}}
table{{border-collapse:collapse;width:100%}}td{{padding:0 12px;vertical-align:top}}td.n{{color:#9aa0a6;text-align:right;user-select:none;width:1%}}
td.n a{{color:inherit;text-decoration:none}}pre{{margin:0;white-space:pre-wrap}}tr:target{{background:#fef7e0}}tr:target td.n{{color:#b06000;font-weight:700}}</style>
</head><body><header>{html.escape(name)} <span style="color:#5f6368;font-weight:400">· read-only · demo-opus.001</span></header><table>{rows}</table>
<script>const t=document.querySelector(location.hash||'#none');if(t)t.scrollIntoView({{block:'center'}});</script></body></html>"""


@app.get("/api/restrictions")
def restrictions() -> list[dict]:
    return [{"key": k, "label": v["label"], "excludes": v["exclude"]} for k, v in RESTRICTIONS.items()]


@app.get("/api/architect-mock")
def architect_mock() -> dict:
    return json.loads((DATA / "architect_mock.json").read_text())


def main() -> None:
    import uvicorn

    uvicorn.run("aistack_demo.server:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
