"""Builds the importable n8n workflow files from the JavaScript in src/.

You do NOT need to run this to use the workflows - the finished files are in
workflows/. It exists so the logic can be edited and tested as normal files.

    python3 build_workflows.py
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "src"
OUT = HERE / "workflows"

GOOGLE = {"googleSheetsOAuth2Api": {"id": "googleSheetsCredential", "name": "Google Sheets account"}}
OPENAI = {"openAiApi": {"id": "openAiCredential", "name": "OpenAI account"}}
INSTAGRAM = {"httpQueryAuth": {"id": "instagramTokenCredential", "name": "Instagram access token"}}
NEVER_ERROR = {"response": {"response": {"neverError": True}}}


def nid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "ia-n8n-only/" + name))


def code(name: str, file: str, pos, mode: str = "runOnceForAllItems") -> dict:
    params = {"jsCode": (SRC / file).read_text()}
    if mode == "runOnceForEachItem":
        params["mode"] = "runOnceForEachItem"
    return {"parameters": params, "id": nid(name), "name": name, "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos}


def config(name: str, fields: list[tuple[str, str]], pos, notes: str) -> dict:
    return {
        "parameters": {
            "assignments": {"assignments": [{"id": nid(name + k), "name": k, "value": v, "type": "string"} for k, v in fields]},
            "options": {},
        },
        "id": nid(name),
        "name": name,
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": pos,
        "notes": notes,
        "notesInFlow": True,
    }


def sheet_ref():
    return {"__rl": True, "mode": "url", "value": "={{ $('Config').first().json.sheetUrl }}"}


def read_sheet(name: str, tab: str, pos) -> dict:
    return {
        "parameters": {"documentId": sheet_ref(), "sheetName": {"__rl": True, "mode": "name", "value": tab}, "options": {}},
        "id": nid(name),
        "name": name,
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": pos,
        "executeOnce": True,
        "credentials": GOOGLE,
    }


def save_sheet(name: str, pos) -> dict:
    return {
        "parameters": {
            "operation": "update",
            "documentId": sheet_ref(),
            "sheetName": {"__rl": True, "mode": "name", "value": "Posts"},
            "columns": {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": ["row_number"], "schema": []},
            # RAW keeps dates as plain text (2026-10-05) instead of locale-formatted dates.
            "options": {"handlingExtraData": "ignoreIt", "cellFormat": "RAW"},
        },
        "id": nid(name),
        "name": name,
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": pos,
        "credentials": GOOGLE,
    }


def if_true(name: str, field: str, pos) -> dict:
    return {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [
                    {"id": nid(name + "c"), "leftValue": f"={{{{ $json.{field} }}}}", "rightValue": True, "operator": {"type": "boolean", "operation": "true", "singleValue": True}}
                ],
                "combinator": "and",
            },
            "looseTypeValidation": True,
            "options": {},
        },
        "id": nid(name),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": pos,
    }


def http(name: str, pos, *, method: str, url: str, credentials: dict | None = None, json_body: str | None = None, form: dict | None = None, query: dict | None = None, timeout: int = 60000) -> dict:
    p: dict = {"method": method, "url": url}
    if credentials and "openAiApi" in credentials:
        p.update({"authentication": "predefinedCredentialType", "nodeCredentialType": "openAiApi"})
    elif credentials:
        p.update({"authentication": "genericCredentialType", "genericAuthType": "httpQueryAuth"})
    if query:
        p.update({"sendQuery": True, "queryParameters": {"parameters": [{"name": k, "value": v} for k, v in query.items()]}})
    if json_body is not None:
        p.update({"sendBody": True, "specifyBody": "json", "jsonBody": json_body})
    if form is not None:
        p.update({"sendBody": True, "contentType": "form-urlencoded", "bodyParameters": {"parameters": [{"name": k, "value": v} for k, v in form.items()]}})
    p["options"] = {**NEVER_ERROR, "timeout": timeout}
    node = {"parameters": p, "id": nid(name), "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": pos}
    if credentials:
        node["credentials"] = credentials
    return node


def link(connections: dict, src: str, dst: str, output: int = 0) -> None:
    outs = connections.setdefault(src, {"main": []})["main"]
    while len(outs) <= output:
        outs.append([])
    outs[output].append({"node": dst, "type": "main", "index": 0})


def sticky(name: str, text: str, pos, width=520, height=420) -> dict:
    return {
        "parameters": {"content": text, "height": height, "width": width, "color": 5},
        "id": nid(name),
        "name": name,
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": pos,
    }


def workflow(name: str, wid: str, nodes: list, connections: dict) -> dict:
    return {
        "name": name,
        "id": wid,
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1", "timezone": "Asia/Kolkata", "saveManualExecutions": True},
        "pinData": {},
        "tags": [],
    }


# ---------------------------------------------------------------------------
# Workflow 1: plan dates + write posts with AI
# ---------------------------------------------------------------------------
def build_plan_and_write() -> dict:
    cfg = "={{ $('Config').first().json"
    nodes = [
        sticky(
            "Read me (1)",
            "## 1. Plan & write posts\n"
            "Runs **every day at 08:00** (and when you click *Test workflow*).\n\n"
            "1. Gives every new topic in the **Posts** tab a Post ID and a date (every N days - set in the **Settings** tab).\n"
            "2. A few days before the date, the AI writes the caption, hashtags and creates the image.\n"
            "3. The row becomes **NEEDS_REVIEW**. A person reads it and sets Status to **APPROVED** (or **REGENERATE**).\n\n"
            "**Setup:** open the **Config** node and paste your Google Sheet link and Cloudinary details. "
            "Then pick your credentials in the Google Sheets and OpenAI nodes.",
            [-420, -320],
            width=560,
            height=330,
        ),
        {"parameters": {"rule": {"interval": [{"field": "days", "triggerAtHour": 8}]}}, "id": nid("Every day 08:00"), "name": "Every day 08:00", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [-400, 60]},
        {"parameters": {}, "id": nid("Test run"), "name": "Test run", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [-400, 240]},
        config(
            "Config",
            [
                ("sheetUrl", "PASTE_YOUR_GOOGLE_SHEET_LINK_HERE"),
                ("cloudinaryCloudName", "PASTE_CLOUDINARY_CLOUD_NAME"),
                ("cloudinaryUploadPreset", "PASTE_CLOUDINARY_UNSIGNED_UPLOAD_PRESET"),
                ("textModel", "gpt-5-mini"),
                ("imageModel", "gpt-image-1"),
                ("openaiBaseUrl", "https://api.openai.com/v1"),
                ("cloudinaryBaseUrl", "https://api.cloudinary.com/v1_1"),
            ],
            [-160, 140],
            "Edit me: sheet link + Cloudinary",
        ),
        read_sheet("Read Settings", "Settings", [60, 140]),
        read_sheet("Read Posts", "Posts", [280, 140]),
        code("Plan posts", "plan_posts.js", [500, 140]),
        if_true("Time to write?", "_generate", [720, 140]),
        code("Build AI request", "build_ai_request.js", [940, 40], "runOnceForEachItem"),
        http(
            "Write post with AI",
            [1160, 40],
            method="POST",
            url=f"{cfg}.openaiBaseUrl }}}}/chat/completions",
            credentials=OPENAI,
            json_body="={{ JSON.stringify($json._openai) }}",
            timeout=180000,
        ),
        code("Check AI text", "check_ai_text.js", [1380, 40], "runOnceForEachItem"),
        if_true("Text OK?", "_ok", [1600, 40]),
        http(
            "Create image with AI",
            [1820, -60],
            method="POST",
            url=f"{cfg}.openaiBaseUrl }}}}/images/generations",
            credentials=OPENAI,
            json_body="={{ JSON.stringify($json._imageRequest) }}",
            timeout=240000,
        ),
        http(
            "Upload image to Cloudinary",
            [2040, -60],
            method="POST",
            url=f"{cfg}.cloudinaryBaseUrl }}}}/{{{{ $('Config').first().json.cloudinaryCloudName }}}}/image/upload",
            json_body=(
                "={{ JSON.stringify({ file: 'data:image/png;base64,' + (($json.data && $json.data[0] && $json.data[0].b64_json) || ''), "
                "upload_preset: $('Config').first().json.cloudinaryUploadPreset, folder: 'instagram-automation' }) }}"
            ),
            timeout=120000,
        ),
        code("Prepare row", "prepare_row.js", [2260, -60], "runOnceForEachItem"),
        save_sheet("Save to Posts sheet", [2480, 140]),
    ]
    c: dict = {}
    link(c, "Every day 08:00", "Config")
    link(c, "Test run", "Config")
    link(c, "Config", "Read Settings")
    link(c, "Read Settings", "Read Posts")
    link(c, "Read Posts", "Plan posts")
    link(c, "Plan posts", "Time to write?")
    link(c, "Time to write?", "Build AI request", 0)
    link(c, "Time to write?", "Save to Posts sheet", 1)  # only a new date was assigned
    link(c, "Build AI request", "Write post with AI")
    link(c, "Write post with AI", "Check AI text")
    link(c, "Check AI text", "Text OK?")
    link(c, "Text OK?", "Create image with AI", 0)
    link(c, "Text OK?", "Save to Posts sheet", 1)  # AI failed: error noted, retried tomorrow
    link(c, "Create image with AI", "Upload image to Cloudinary")
    link(c, "Upload image to Cloudinary", "Prepare row")
    link(c, "Prepare row", "Save to Posts sheet")
    return workflow("Instagram - 1. Plan & write posts (AI)", "iaOnlyPlanWrite01", nodes, c)


# ---------------------------------------------------------------------------
# Workflow 2: publish approved posts at their time
# ---------------------------------------------------------------------------
def build_publish() -> dict:
    cfg = "={{ $('Config').first().json"
    nodes = [
        sticky(
            "Read me (2)",
            "## 2. Publish approved posts\n"
            "Runs **every 15 minutes**.\n\n"
            "Publishes rows whose Status is **APPROVED** and whose date/time has arrived, using the official Instagram API. "
            "Writes the Instagram link back to the sheet (Status **PUBLISHED**) or the reason it failed (Status **FAILED**).\n\n"
            "Only APPROVED rows are ever published. A failed post is never retried automatically, so nothing is posted twice.\n\n"
            "**Setup:** open **Config**: paste your Google Sheet link and your Instagram account ID. "
            "Pick your credentials in the Google Sheets nodes and the Instagram nodes.",
            [-420, -340],
            width=560,
            height=350,
        ),
        {"parameters": {"rule": {"interval": [{"field": "minutes", "minutesInterval": 15}]}}, "id": nid("Every 15 minutes"), "name": "Every 15 minutes", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [-400, 60]},
        {"parameters": {}, "id": nid("Test run 2"), "name": "Test run", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [-400, 240]},
        config(
            "Config",
            [
                ("sheetUrl", "PASTE_YOUR_GOOGLE_SHEET_LINK_HERE"),
                ("instagramAccountId", "PASTE_YOUR_INSTAGRAM_ACCOUNT_ID"),
                ("instagramApiBase", "https://graph.instagram.com/v25.0"),
            ],
            [-160, 140],
            "Edit me: sheet link + Instagram account ID",
        ),
        read_sheet("Read Settings", "Settings", [60, 140]),
        read_sheet("Read Posts", "Posts", [280, 140]),
        code("Find posts to publish", "find_posts_to_publish.js", [500, 140]),
        if_true("Publish now?", "_publish", [720, 140]),
        save_sheet("Mark as publishing", [940, 40]),
        http(
            "Create Instagram container",
            [1160, 40],
            method="POST",
            url=f"{cfg}.instagramApiBase }}}}/{{{{ $('Config').first().json.instagramAccountId }}}}/media",
            credentials=INSTAGRAM,
            form={"image_url": "={{ $('Find posts to publish').item.json['Image URL'] }}", "caption": "={{ $('Find posts to publish').item.json._caption }}"},
        ),
        {"parameters": {"amount": 30, "unit": "seconds"}, "id": nid("Wait 30 seconds"), "name": "Wait 30 seconds", "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "position": [1380, 40], "webhookId": nid("wait-webhook")},
        http(
            "Check container",
            [1600, 40],
            method="GET",
            url=f"{cfg}.instagramApiBase }}}}/{{{{ $('Create Instagram container').item.json.id }}}}",
            credentials=INSTAGRAM,
            query={"fields": "status_code"},
        ),
        http(
            "Publish to Instagram",
            [1820, 40],
            method="POST",
            url=f"{cfg}.instagramApiBase }}}}/{{{{ $('Config').first().json.instagramAccountId }}}}/media_publish",
            credentials=INSTAGRAM,
            form={"creation_id": "={{ $('Create Instagram container').item.json.id }}"},
        ),
        http(
            "Get post link",
            [2040, 40],
            method="GET",
            url=f"{cfg}.instagramApiBase }}}}/{{{{ $json.id }}}}",
            credentials=INSTAGRAM,
            query={"fields": "permalink"},
        ),
        code("Publish result", "publish_result.js", [2260, 40], "runOnceForEachItem"),
        save_sheet("Save to Posts sheet", [2480, 140]),
    ]
    c: dict = {}
    link(c, "Every 15 minutes", "Config")
    link(c, "Test run", "Config")
    link(c, "Config", "Read Settings")
    link(c, "Read Settings", "Read Posts")
    link(c, "Read Posts", "Find posts to publish")
    link(c, "Find posts to publish", "Publish now?")
    link(c, "Publish now?", "Mark as publishing", 0)
    link(c, "Publish now?", "Save to Posts sheet", 1)  # PROBLEM rows
    link(c, "Mark as publishing", "Create Instagram container")
    link(c, "Create Instagram container", "Wait 30 seconds")
    link(c, "Wait 30 seconds", "Check container")
    link(c, "Check container", "Publish to Instagram")
    link(c, "Publish to Instagram", "Get post link")
    link(c, "Get post link", "Publish result")
    link(c, "Publish result", "Save to Posts sheet")
    return workflow("Instagram - 2. Publish approved posts", "iaOnlyPublish0002", nodes, c)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for fname, wf in (("1-plan-and-write-posts.json", build_plan_and_write()), ("2-publish-approved-posts.json", build_publish())):
        (OUT / fname).write_text(json.dumps(wf, indent=2, ensure_ascii=False) + "\n")
        print("wrote", OUT / fname)
