"""Console tests against the local demo repository (import into a temporary data dir, plan set to enterprise/Business)."""
from __future__ import annotations

import os
import tempfile

import pytest

DEMO = os.environ.get("ORIGIT_DEMO_REPO", "/home/timotej/Documents/bcco/code/origit-demo-payments-api")
_TMP = tempfile.mkdtemp(prefix="origit-console-test-")
os.environ["ORIGIT_DATA_DIR"] = _TMP
os.environ["CONSOLE_TOKEN"] = "test-token"
os.environ.pop("GIT_SSH_HOST", None)
os.environ.pop("BOB_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from app import gitrepo as G  # noqa: E402
from app.main import app  # noqa: E402

ORG, NAME = "acme-payments", "payments-api"
FULL = f"{ORG}/{NAME}"
TOKEN = {"X-Origit-Token": "test-token"}
NEEDLE = "fast-pay-utils"

pytestmark = pytest.mark.skipif(not os.path.isdir(DEMO), reason=f"demo repo not found at {DEMO}")


@pytest.fixture(scope="module")
def client():
    G.import_from_url(ORG, NAME, DEMO, "demo")
    G.set_meta(ORG, NAME, plan="enterprise")
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def head(client):
    return client.get(f"/api/{FULL}/commits").json()[0]["sha"]


def test_health(client):
    j = client.get("/api/health").json()
    assert j["ok"] and j["repos"] >= 1 and "bob" in j


def test_repos(client):
    repos = client.get("/api/repos").json()
    r = next(x for x in repos if x["full_name"] == FULL)
    assert r["plan"] == "enterprise" and r["records"] > 0


def test_commits_have_session_labels_and_reasons(client):
    rows = client.get(f"/api/{FULL}/commits").json()
    agent = [r for r in rows if r["record"] and r["record"]["actor"]["kind"] != "human"]
    assert agent
    for r in agent:
        assert r["session_label"].startswith("#") and r["session_id"] == r["record"]["session"]["id"]
    for r in rows:
        assert "reasons" in r and "reason" in r
        for f in r["prefilter"]["findings"]:
            assert f["reason"]
    assert any(r["reasons"] for r in rows)
    labels = {r["session_label"] for r in agent}
    assert len(labels) == len({r["session_id"] for r in agent})
    assert isinstance(rows[0]["evidence"], bool)


def test_taint_api(client):
    t = client.get(f"/api/{FULL}/taint", params={"q": NEEDLE}).json()
    assert len(t["affected"]) > 0
    assert t["session_labels"] and all(v.startswith("#") for v in t["session_labels"].values())
    assert set(t["session_labels"]) == set(t["sessions"])
    assert "files_primary" in t and "files_secondary" in t
    assert set(t["files_primary"]) | set(t["files_secondary"]) == set(t["files_written"])
    assert not any("node_modules/" in f or ".test." in f for f in t["files_primary"])
    assert t["first_read"]["label"].startswith("#")
    assert all(a["session_label"].startswith("#") for a in t["affected"])


def test_commit_api(client, head):
    j = client.get(f"/api/{FULL}/commit/{head}").json()
    assert j["sha"] == head and "session_label" in j and "reasons" in j and "diff" not in j


def test_security_api(client):
    m = client.get(f"/api/{FULL}/security").json()
    assert m["categories"] and m["grid"]
    assert any(g["session_label"] for g in m["grid"])


def test_review_status_and_review_all_without_bob(client):
    st = client.get(f"/api/{FULL}/review-status").json()
    assert st and all({"reviewed", "source", "ran_at", "queued"} <= set(v) for v in st.values())
    r = client.post(f"/api/{FULL}/review-all", headers=TOKEN)
    assert r.status_code == 200
    j = r.json()
    assert "scheduled" in j and j["scheduled"] == 0 and j["candidates"] == len(st)
    assert client.post(f"/api/{FULL}/review-all").status_code == 401


def test_hook_records_push(client, head):
    r = client.post("/api/hooks/post-receive", headers=TOKEN, json={"org": ORG, "repo": NAME, "updates": [{"old": "0" * 40, "new": head, "ref": "refs/heads/main"}]})
    assert r.status_code == 200
    j = r.json()
    assert j["commits"][0] == head and j["review_scheduled"] == 0
    assert client.get(f"/api/{FULL}/pushes").json()[0]["id"] == j["id"]


@pytest.mark.parametrize("path", ["/", f"/{FULL}", f"/{FULL}/commits", "/commit/HEAD", f"/{FULL}/taint?q={NEEDLE}", f"/{FULL}/security", f"/{FULL}/pushes", "/explore", f"/{ORG}"])
def test_html_pages(client, head, path):
    if path == "/commit/HEAD":
        path = f"/{FULL}/commit/{head}"
    r = client.get(path)
    assert r.status_code == 200, path
    html = r.text
    assert "root@" not in html
    assert "IBM Bob not configured" in html
    assert "Bob never edits a record or a taint result" in html
    assert "Enterprise" not in html


def test_landing_is_real(client):
    html = client.get("/").text
    assert f"origit taint {NEEDLE}" in html and "commits affected" in html  # computed live from the demo repo
    assert "Sessions:   #" in html


def test_taint_page_split(client):
    html = client.get(f"/{FULL}/taint", params={"q": NEEDLE}).text
    assert "also touched (" in html and "session " in html


def test_commit_page_labels(client):
    rows = client.get(f"/api/{FULL}/commits").json()
    agent = next(r for r in rows if r["record"] and r["record"]["actor"]["kind"] != "human")
    html = client.get(f"/{FULL}/commit/{agent['sha']}").text
    assert f'title="session {agent["session_id"]}"' in html and f'>{agent["session_label"]}<' in html


def test_business_label(client):
    html = client.get(f"/{FULL}").text
    assert ">Business<" in html
    assert "git@" not in html and "root@" not in html and "Push here" not in html  # demo dashboard: no push instructions



def test_push_evidence_and_security_page(client):
    r = client.get(f"/api/{FULL}/push-evidence")
    assert r.status_code == 200
    cards = r.json()
    assert cards and all("agg" in c and "categories" in c["agg"] and len(c["agg"]["categories"]) == 10 for c in cards)
    html = client.get(f"/{FULL}/security").text
    assert "The ten checks" in html and "Hidden or injected instructions" in html and "Latest pushes" in html
    assert client.get(f"/{FULL}/pushes").status_code == 200


def test_readonly_guard_blocks_plan_and_sync(client):
    from app.config import settings
    object.__setattr__(settings, "readonly", True)
    try:
        r = client.post(f"/api/{FULL}/plan", json={"plan": "free"}, headers={"X-Origit-Token": settings.token})
        assert r.status_code == 403
        r = client.post(f"/api/{FULL}/sync", headers={"X-Origit-Token": settings.token})
        assert r.status_code == 403
    finally:
        object.__setattr__(settings, "readonly", False)
