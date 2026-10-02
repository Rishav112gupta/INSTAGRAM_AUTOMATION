"""End-to-end test of both n8n workflows inside a real n8n (Docker), with fake services.

Google Sheets nodes are swapped for Code nodes holding sample rows, and the
OpenAI/Cloudinary/Instagram URLs point to tests/mock_services.py. Nothing real is
called and nothing is posted.

Requires Docker.  Run from the n8n-only folder:   python3 tests/run_tests.py
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
ROOT = HERE.parent
IMAGE = "n8nio/n8n:2.41.6"
MOCK = "http://127.0.0.1:9999"
TZ = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(TZ).date()

SETTINGS = [
    {"Setting": "Company Name", "Value": "Acme Academy"},
    {"Setting": "Verified Facts", "Value": "Crash course fee: Rs 3,500\nCentre: Main Road, Pune"},
    {"Setting": "Post Every N Days", "Value": "4"},
    {"Setting": "Default Post Time", "Value": "18:00"},
    {"Setting": "Timezone", "Value": "Asia/Kolkata"},
    {"Setting": "Generate Days Before", "Value": "3"},
    {"Setting": "Start Date", "Value": TODAY.isoformat()},
    {"Setting": "Default Hashtags", "Value": "acmeacademy"},
]
COLS = ["Post ID", "Topic", "Category", "Target Audience", "Important Info", "Call To Action", "Scheduled Date", "Post Time", "Status", "Headline", "Caption", "Hashtags", "Image URL", "Review Notes", "Instagram URL", "Instagram Media ID", "Container ID", "Error", "Last Updated"]


def row(n: int, **values) -> dict:
    r = {c: "" for c in COLS}
    r.update(values)
    r["row_number"] = n
    return r


POSTS_1 = [
    row(2, Topic="Exam tips", Category="EXAM"),  # new -> planned for today -> written now
    row(3, Topic="Batch kickoff", Category="BATCH"),  # new -> planned +4 days -> only dated
    row(4, **{"Post ID": "P0007", "Topic": "Revision plan", "Status": "REGENERATE", "Scheduled Date": (TODAY + timedelta(days=10)).isoformat(), "Review Notes": "Make it shorter"}),
    row(5, Topic=""),  # empty row -> ignored
    row(6, **{"Post ID": "P0008", "Topic": "FAILME topic", "Status": "PLANNED", "Scheduled Date": (TODAY + timedelta(days=1)).isoformat(), "Post Time": "18:00"}),
    row(7, **{"Post ID": "P0002", "Topic": "Old post", "Status": "PUBLISHED", "Scheduled Date": (TODAY - timedelta(days=4)).isoformat()}),
]
past = (datetime.now(TZ) - timedelta(hours=1))
POSTS_2 = [
    row(2, **{"Post ID": "P0001", "Topic": "Due", "Status": "APPROVED", "Scheduled Date": past.date().isoformat(), "Post Time": past.strftime("%H:%M"), "Caption": "Hello", "Hashtags": "a b", "Image URL": "https://res.cloudinary.com/demo/x.jpg"}),
    row(3, **{"Post ID": "P0002", "Topic": "Future", "Status": "APPROVED", "Scheduled Date": (TODAY + timedelta(days=3)).isoformat(), "Post Time": "18:00", "Caption": "Later", "Image URL": "https://x/y.jpg"}),
    row(4, **{"Post ID": "P0003", "Topic": "No image", "Status": "APPROVED", "Scheduled Date": TODAY.isoformat(), "Post Time": "00:00", "Caption": "Hi"}),
    row(5, **{"Post ID": "P0004", "Topic": "Done", "Status": "PUBLISHED", "Instagram Media ID": "999", "Scheduled Date": TODAY.isoformat(), "Caption": "x", "Image URL": "https://x/y.jpg"}),
    row(6, **{"Post ID": "P0005", "Topic": "Bad token", "Status": "APPROVED", "Scheduled Date": past.date().isoformat(), "Post Time": past.strftime("%H:%M"), "Caption": "TOKENFAIL", "Image URL": "https://res.cloudinary.com/demo/z.jpg"}),
    row(7, **{"Post ID": "P0006", "Topic": "Needs review", "Status": "NEEDS_REVIEW", "Scheduled Date": past.date().isoformat(), "Caption": "x", "Image URL": "https://x/y.jpg"}),
]


def to_test(wf: dict, posts: list, config: dict) -> dict:
    wf = copy.deepcopy(wf)
    wf["id"] = wf["id"] + "T"
    for n in wf["nodes"]:
        if n["type"] == "n8n-nodes-base.googleSheets":
            n.pop("credentials", None)
            n["type"], n["typeVersion"] = "n8n-nodes-base.code", 2
            if n["parameters"].get("operation") == "update":
                n["parameters"] = {"jsCode": "return $input.all();"}  # 'save' = pass through
            else:
                data = SETTINGS if n["name"] == "Read Settings" else posts
                n["parameters"] = {"jsCode": f"return {json.dumps(data, ensure_ascii=False)}.map(j => ({{ json: j }}));"}
        if n["name"] == "Config":
            for a in n["parameters"]["assignments"]["assignments"]:
                if a["name"] in config:
                    a["value"] = config[a["name"]]
    return wf


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def run_data(container: str, wid: str) -> dict:
    out = sh(["docker", "exec", "-e", "N8N_RUNNERS_BROKER_PORT=5690", container, "n8n", "execute", f"--id={wid}", "--rawOutput"], timeout=300).stdout
    dec = json.JSONDecoder()
    for i, ch in enumerate(out):
        if ch == "{":
            try:
                data, _ = dec.raw_decode(out[i:])
                return data.get("data", data)["resultData"]
            except Exception:
                continue
    raise RuntimeError("no JSON result:\n" + out[-3000:])


def items(result: dict, node: str) -> list[dict]:
    runs = result["runData"].get(node, [])
    out = []
    for r in runs:
        for branch in r["data"]["main"]:
            out += [i["json"] for i in (branch or [])]
    return out


FAILURES = []


def check(cond: bool, label: str):
    print(("  PASS " if cond else "  FAIL ") + label)
    if not cond:
        FAILURES.append(label)


def main() -> int:
    sys.path.insert(0, str(ROOT))
    import build_workflows

    mock = subprocess.Popen([sys.executable, str(HERE / "mock_services.py"), "9999"])
    tmp = Path(tempfile.mkdtemp())
    tmp.chmod(0o777)
    wf1 = to_test(build_workflows.build_plan_and_write(), POSTS_1, {
        "openaiBaseUrl": f"{MOCK}/v1", "cloudinaryBaseUrl": f"{MOCK}/v1_1", "cloudinaryCloudName": "demo", "cloudinaryUploadPreset": "unsigned_test", "sheetUrl": "https://docs.google.com/spreadsheets/d/test/edit"})
    wf2 = to_test(build_workflows.build_publish(), POSTS_2, {"instagramApiBase": f"{MOCK}/v25.0", "instagramAccountId": "17841400000000000", "sheetUrl": "https://docs.google.com/spreadsheets/d/test/edit"})
    (tmp / "wf1.json").write_text(json.dumps(wf1))
    (tmp / "wf2.json").write_text(json.dumps(wf2))
    (tmp / "creds.json").write_text(json.dumps([
        {"id": "openAiCredential", "name": "OpenAI account", "type": "openAiApi", "data": {"apiKey": "test-openai-key", "url": "https://api.openai.com/v1"}},
        {"id": "instagramTokenCredential", "name": "Instagram access token", "type": "httpQueryAuth", "data": {"name": "access_token", "value": "test-token"}},
    ]))
    for f in tmp.iterdir():
        f.chmod(0o666)
    name = "ia-n8n-only-test"
    sh(["docker", "rm", "-f", name])
    started = sh(["docker", "run", "-d", "--name", name, "--network", "host", "-e", "N8N_LISTEN_ADDRESS=127.0.0.1", "-e", "N8N_PORT=5699", "-e", "N8N_DIAGNOSTICS_ENABLED=false",
                  "-e", "GENERIC_TIMEZONE=Asia/Kolkata", "-e", "N8N_ENCRYPTION_KEY=testkeytestkeytestkey", "-v", f"{tmp}:/data:ro", IMAGE])
    if started.returncode:
        print(started.stderr)
        return 1
    try:
        time.sleep(15)
        for args in (["import:credentials", "--input=/data/creds.json"], ["import:workflow", "--input=/data/wf1.json"], ["import:workflow", "--input=/data/wf2.json"]):
            r = sh(["docker", "exec", name, "n8n", *args])
            if "Successfully" not in r.stdout + r.stderr:
                print(r.stdout, r.stderr)
                return 1

        print("Workflow 1: plan & write posts")
        res = run_data(name, wf1["id"])
        check(res.get("error") is None, f"workflow finished without error ({(res.get('error') or {}).get('message')})")
        saved = {r["row_number"]: r for r in items(res, "Save to Posts sheet")}
        r2, r3, r4, r6 = saved.get(2, {}), saved.get(3, {}), saved.get(4, {}), saved.get(6, {})
        if "--debug" in sys.argv:
            print(json.dumps({k: {c: v for c, v in r.items() if c in ("Post ID", "Status", "Scheduled Date", "Headline", "Hashtags", "Review Notes", "Error", "Image URL")} for k, r in saved.items()}, indent=1, ensure_ascii=False))
        check(r2.get("Post ID") == "P0009" and r2.get("Scheduled Date") == TODAY.isoformat(), "new topic got next Post ID and today's date")
        check(r2.get("Status") == "NEEDS_REVIEW" and "made simple" in r2.get("Headline", ""), "post due soon was written by AI -> NEEDS_REVIEW")
        check(r2.get("Image URL", "").startswith("https://res.cloudinary.com/demo/image/upload/c_fill,g_auto,w_1080,h_1350/f_jpg,q_90/") and r2["Image URL"].endswith(".jpg"), "image converted to 1080x1350 JPEG link")
        check("₹4,999" in r2.get("Review Notes", "") and "[EXAM DATE]" in r2.get("Review Notes", "") and "Exact exam date" in r2.get("Review Notes", ""), "invented price, placeholder and missing info are flagged")
        check(r2.get("Hashtags") == "examtips students studytips acmeacademy", "hashtags cleaned, de-duplicated, default added")
        check(r3.get("Status") == "PLANNED" and r3.get("Scheduled Date") == (TODAY + timedelta(days=4)).isoformat() and r3.get("Post ID") == "P0010", "second topic planned 4 days later, not written yet")
        check(r4.get("Status") == "NEEDS_REVIEW" and r4.get("Headline") == "Revision plan made simple", "REGENERATE row was rewritten")
        check(r6.get("Status") == "PLANNED" and "AI writing failed" in r6.get("Error", ""), "AI failure noted, row kept for retry")
        check(5 not in saved and 7 not in saved, "empty and published rows ignored")
        check(not any(k in r2 for k in ("_openai", "_imageRequest", "_ok")), "internal AI fields not written to the sheet row")

        print("Workflow 2: publish approved posts")
        res = run_data(name, wf2["id"])
        check(res.get("error") is None, f"workflow finished without error ({(res.get('error') or {}).get('message')})")
        saved = {}
        for r in items(res, "Save to Posts sheet"):
            saved[r["row_number"]] = r
        p2, p4, p6 = saved.get(2, {}), saved.get(4, {}), saved.get(6, {})
        check(p2.get("Status") == "PUBLISHED" and p2.get("Instagram URL", "").startswith("https://www.instagram.com/p/MOCK"), "due APPROVED post published, link saved")
        check(p2.get("Instagram Media ID", "").startswith("180") and p2.get("Container ID", "").startswith("179"), "media id and container id saved")
        check(3 not in saved, "future post not published yet")
        check(p4.get("Status") == "PROBLEM" and "Image URL" in p4.get("Error", ""), "approved post without image -> PROBLEM with reason")
        check(5 not in saved and 7 not in saved, "PUBLISHED and NEEDS_REVIEW rows untouched")
        check(p6.get("Status") == "FAILED" and "token" in p6.get("Error", "").lower(), "expired token -> FAILED with clear instructions")
        state = json.load(urllib.request.urlopen(f"{MOCK}/state"))
        check(len(state["published"]) == 1, "exactly one post sent to (fake) Instagram")
        cap = list(state["containers"].values())[0]
        check(cap["caption"] == "Hello\n\n#a #b" and cap["image_url"] == "https://res.cloudinary.com/demo/x.jpg", "caption + hashtags and image URL sent correctly")
    finally:
        logs = sh(["docker", "logs", name]).stdout
        sh(["docker", "rm", "-f", name])
        mock.terminate()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED")
        print(logs[-2000:])
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
