---
name: crm-analyst-query
description: "Triggered when a PM or sales manager asks an analytics question about veris.ai product or marketing data — traffic sources, referrers, funnels, conversions, signups, trends, who-did-what. Translates the question into one HogQL query against PostHog, runs it via exec, and replies with a short answer plus the supporting rows. Read-only: never sends email or mutates anything. Trigger phrases: 'who is coming from', 'how many', 'top sources', 'traffic from', 'referrer', 'funnel', 'conversion', 'signups', 'trend', 'visitors', 'analytics', 'where are users coming from', 'utm'."
metadata:
  openclaw:
    emoji: "📊"
---

# CRM Analyst — PostHog Query

A PM or sales manager asked an analytics question. Translate it to **one** HogQL query against PostHog, run it, and answer inline with the result. This skill is **read-only** — it never sends email, posts externally, or mutates anything.

## When to Use

USE when the user asks about product/marketing analytics:
- Traffic-source / referrer attribution ("who's coming from ChatGPT to the landing page?", "top traffic sources last 30 days")
- Funnels / conversion ("how many landing-page visitors started signup?")
- Trends over time ("ChatGPT signups per day this week")
- Counts / breakdowns over events or people

DON'T use when:
- The user asks to start/check the sales **pipeline** or find a lead to reach out to → that's `nemo-sales-crm-pipeline-check`.
- The user replies `approve` / `reject` / `edit:` → that's `nemo-sales-crm-approval`.

## Required Environment

- `POSTHOG_API_HOST` — PostHog base URL (e.g. `https://us.posthog.com`)
- `POSTHOG_PROJECT_ID` — your PostHog project's numeric id
- `POSTHOG_API_KEY` — Personal API key with `query:read` + `person:read`

## How to Use

**EXECUTION CONSTRAINT — run here, in this session.** Do NOT call `sessions_list` / `sessions_send` / `sessions_history` or delegate. Make the PostHog call directly with the `exec` tool running a Python heredoc (this openclaw build has no `code_execution` tool — `exec` with `python3 - <<'PY' … PY` is the equivalent).

### Step 1 — Pick the query

Match the question to a template (substitute the time window and any filter term the user gave), or write a freeform query within the **HogQL rules** below.

**T1 — Traffic-source attribution.** Filtered ("who's coming from <X>?"):
```sql
SELECT e.distinct_id, p.properties.email AS email,
       e.properties.$referring_domain AS referrer, e.properties.utm_source AS utm_source,
       count() AS views
FROM events e
LEFT JOIN persons p ON e.person_pk = p.id
WHERE e.event = '$pageview'
  AND e.properties.$referring_domain ILIKE '%chatgpt%'
  AND e.timestamp > now() - INTERVAL 720 HOUR
GROUP BY e.distinct_id, email, referrer, utm_source
ORDER BY views DESC LIMIT 50
```
Grouped ("top sources") — drop the `ILIKE` line and:
```sql
SELECT e.properties.$referring_domain AS source,
       count(DISTINCT e.distinct_id) AS visitors, count() AS views
FROM events e
WHERE e.event = '$pageview' AND e.timestamp > now() - INTERVAL 720 HOUR
GROUP BY source ORDER BY visitors DESC LIMIT 25
```

**T2 — Funnel** (visited → started → completed):
```sql
SELECT
  count(DISTINCT CASE WHEN event='$pageview' THEN distinct_id END) AS visited,
  count(DISTINCT CASE WHEN event='signup_started' THEN distinct_id END) AS started,
  count(DISTINCT CASE WHEN event='signup_completed' THEN distinct_id END) AS completed
FROM events WHERE timestamp > now() - INTERVAL 720 HOUR
```

**T3 — Trend over time** (per day). `toDate()` is NOT supported — use `substring`:
```sql
SELECT substring(e.timestamp, 1, 10) AS day, count(DISTINCT e.distinct_id) AS visitors
FROM events e
WHERE e.event='$pageview' AND e.properties.$referring_domain ILIKE '%chatgpt%'
GROUP BY day ORDER BY day
```

### Step 2 — Run it

Call `exec` with this command, replacing `HOGQL` with your query from Step 1:
```
tool: exec
arguments:
  command: |
    python3 - <<'PY'
    import json, os, urllib.request, sys
    hogql = """HOGQL"""
    # OpenShell exec does NOT inherit gateway env.vars; read creds from the
    # secret file baked at /sandbox/.secrets/posthog.env instead.
    _sec = {}
    with open("/sandbox/.secrets/posthog.env") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and "=" in _l and _l[0] != "#":
                _k, _v = _l.split("=", 1); _sec[_k] = _v
    host = (_sec.get("POSTHOG_API_HOST") or "https://us.posthog.com").rstrip("/")
    pid = _sec.get("POSTHOG_PROJECT_ID", "")
    key = _sec.get("POSTHOG_API_KEY", "")
    if not key or not pid:
        print(json.dumps({"error": "POSTHOG_API_KEY / POSTHOG_PROJECT_ID missing"})); sys.exit(1)
    req = urllib.request.Request(
        f"{host}/api/projects/{pid}/query/",
        data=json.dumps({"query": {"kind": "HogQLQuery", "query": hogql}}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(json.dumps({"http_status": e.code, "body": e.read().decode("utf-8","replace")[:1000]})); sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)})); sys.exit(1)
    print(json.dumps({"columns": data.get("columns"), "results": data.get("results")})[:40000])
    PY
```

### HogQL rules — the backend rejects everything else

- `SELECT` only. Tables: `events`, `persons`, `person_distinct_ids` ONLY.
- Property access: `properties.$referring_domain`, `properties.utm_source`, `properties.$pathname`, etc. — works on `events` and on a joined `persons` alias (`p.properties.email`).
- Time filter: `timestamp > now() - INTERVAL N HOUR` (bare `INTERVAL N HOUR`; never a quoted interval).
- Join people via `events.person_pk = persons.id` (or `person_distinct_ids`).
- Always include a `LIMIT` (≤ 200).
- Do NOT use: CTEs (`WITH … AS`), `countIf` / `arrayJoin`, `toDate()` / `toStartOfDay()` (use `substring(timestamp,1,10)` for day buckets), or event names you haven't confirmed exist.
- On an error response (`http_status` / `error`), read it, fix the query, retry — **at most 3 times**, then report the failure honestly. **Never invent numbers.**

### Step 3 — Answer

Reply with one plain-language sentence answering the question, then the rows in a **code block** (renders cleanly in Slack — do NOT use a Markdown pipe-table). Cap at ~15 rows ("showing top N" if more). If zero rows, say so plainly.

Example:
```
2 people hit the landing page from ChatGPT in the last 30 days:

  email           referrer      utm_source   views
  dana@acme.com   chatgpt.com   chatgpt      1
  frank@big.co    chatgpt.com   chatgpt      1
```

## Hard rules
- **Read-only.** Never send email, never post externally, never call a send/message tool. (Outbound email is the `nemo-sales-crm-approval` skill, and only after an explicit `approve`.)
- **Confidentiality.** Answer aggregate / attribution questions; do not dump raw PII beyond what the question needs.
