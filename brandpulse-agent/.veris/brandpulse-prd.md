# BrandPulse — Product Requirements Document

**Status:** Draft v2
**Owner:** BrandPulse team
**Platform:** OpenClaw (personal AI assistant)

---

## 1. Summary

BrandPulse is a scheduled personal AI agent that delivers a daily one-page Slack digest about a brand you care about — your company, a competitor, a customer, a portfolio company. It wakes on a cron, searches the web, writes a structured summary grounded in what it found, posts it to a Slack channel, and exits.

It is built as a stock OpenClaw agent: runs on your own machine, uses your own model credentials, posts through your own Slack workspace.

## 2. Problem

People who own a brand-shaped responsibility (founders, PMMs, comms, investors, CS leads) need consistent daily situational awareness on a handful of brands. The status quo is:

- Manually skim Google News, X, HN, niche subreddits, press release wires.
- Maintain Google Alerts that are noisy, late, and email-shaped.
- Pay for a marketing-intelligence SaaS that lives in a tab nobody opens.
- Ask a junior teammate to do it (expensive, inconsistent, doesn't scale to N brands).

None of these land in the surface where the team already talks: Slack.

## 3. Goal

Replace "someone skims the internet for me every morning" with a scheduled agent. Specifically:

- One digest per brand, per morning, in the channel for that brand.
- Grounded in real search results, with citations.
- Same shape every day so it's skimmable in 30 seconds.
- Runs unattended; operator only intervenes on config changes.

## 4. Non-goals

- Not a chatbot. Interactive Q&A is a side benefit of OpenClaw, not the product.
- Not a real-time alerting system. Daily cadence is the contract.
- Not an analytics dashboard. No charts, no historical rollups inside the agent.
- Not a multi-tenant SaaS. One operator, one OpenClaw install, N brands.

## 5. Users

| Persona | What they want |
|---|---|
| **Founder / exec** | Daily read on their own company's external chatter + 2-3 competitors. |
| **PMM / comms** | Coverage of a launch, sentiment around the brand, who's writing about us. |
| **Investor** | Daily pulse on each portfolio company, surfaced without N tabs. |
| **CS / account lead** | Daily pulse on top accounts — funding, exec changes, press. |

## 6. How it works

BrandPulse is one OpenClaw agent definition. The operator configures it once in `~/.openclaw/openclaw.json`, then schedules it via cron (or `launchd`, or any scheduler).

```
cron (8:55am)
  └─> openclaw agent --local --agent brandpulse \
        --deliver --reply-channel slack --reply-to C_BRAND_ACME \
        --message "Daily pulse: Acme Corp. Last 24h."
        │
        ├─ validate the trigger (brand + window + modifiers)
        ├─ tool: web_search   (5–8 queries, scoped to the window/modifiers)
        ├─ model: summarize the results into the digest template
        └─ channel: slack.chat.postMessage to #brand-acme
```

One invocation = one brand = one digest = one Slack post. To track N brands, the operator schedules N cron entries with different `--reply-to` and `--message` values.

**Tooling note.** BrandPulse uses a single tool: `web_search`. It grounds the digest in the titles, snippets, and URLs that search returns — it does not fetch full page bodies. Citations are the search-result URLs.

## 7. The daily prompt (trigger format)

The `--message` value cron passes to the agent. This is the contract between the scheduler and the agent.

### Required shape

```
Daily pulse: <BRAND>. Last <WINDOW>.
```

- **`<BRAND>`** — the canonical name of the brand. Use the form the brand uses for itself ("Stripe", not "stripe.com"; "Anthropic", not "anthropic.ai").
- **`<WINDOW>`** — the lookback. Default `24h`. Other accepted values: `48h`, `7d`. Anything else is rejected (see Validation).

### Optional modifiers

Appended after the required shape, comma-separated:

- `focus: <topic>` — bias search toward a topic (e.g. `focus: hiring`, `focus: product launches`).
- `exclude: <topic>` — drop a topic from the digest (e.g. `exclude: stock price`).
- `region: <region>` — geo-bias search (e.g. `region: EMEA`).

### Examples

```
Daily pulse: Acme Corp. Last 24h.
Daily pulse: Stripe. Last 24h. focus: product launches
Daily pulse: Anthropic. Last 7d. focus: hiring, exclude: stock price
Daily pulse: OpenAI. Last 24h. region: EMEA
```

### Validation (agent behavior)

The agent validates the trigger before searching and **refuses** — posting a single short message that names the problem and the accepted format, with no digest — when:

- the window is missing or not exactly `24h` / `48h` / `7d` (e.g. "last 3d", "last week");
- more than one brand is requested in a single message;
- the message contains contradictory time references (e.g. a 24h window plus a "last week" focus);
- the trigger is otherwise malformed.

Operators should send the structured form above and one brand per invocation; the agent enforces this rather than guessing.

## 8. The digest (output format)

Every digest posts to Slack in the same shape. The operator can change the template by editing `openclaw.json`; what matters is that it's stable across days.

```
*<BRAND> — Daily Pulse — <DATE>*
_Window: last <WINDOW> · <N> sources_

*Headlines*
• <one-line headline> — <source>
• <one-line headline> — <source>
• <one-line headline> — <source>

*What's new*
<2–4 sentence summary of the most material development, grounded in the search results.>

*Sentiment*
<one sentence: positive / mixed / negative, with the dominant theme.>

*Worth a click*
• <title> — <url>
• <title> — <url>
• <title> — <url>

_Generated by BrandPulse · model: <model>_
```

### Output rules

- **Citations are mandatory.** Every claim in "What's new" must trace to a URL in "Worth a click" or "Headlines". If the model can't ground it in a search result, omit it.
- **No invented sources.** If search returned nothing usable or in-window, the digest says so explicitly ("No material coverage in the last <WINDOW>") rather than padding.
- **Length cap.** Under 350 words. The digest is meant to be skimmed in 30 seconds.
- **Tone.** Neutral, news-desk register. No marketing language, no hedging boilerplate.
- **Failure mode.** If the model can't produce a digest (no sources, tool failure), post a short failure line — never silently exit 0.

## 9. Interactive use

Same agent, same config, DM in Slack instead of cron. Supported queries:

- "What's the chatter on our last product launch?"
- "Anything new on $COMPETITOR before my 2pm?"
- "Pull the top 3 stories on Anthropic from the last week."

The agent uses the same tool (`web_search`) and the same digest template, scaled down to the question. Interactive use is a convenience, not a separate product surface.

## 10. Configuration

Lives in `~/.openclaw/openclaw.json`. Per brand the operator sets:

| Field | Purpose |
|---|---|
| `agent.name` | `brandpulse` (or a brand-specific variant). |
| `agent.prompt` | System prompt with the trigger contract, validation rules, and digest template. |
| `agent.tools` | Allowlist: `web_search`. Nothing else. |
| `agent.model` | Default model for the digest. |
| `channels.slack.token` | OAuth token for the workspace. |
| `channels.slack.default_channel` | Fallback; cron passes per-brand `--reply-to`. |

Cron entries supply the per-brand `--reply-to` channel ID and the `--message` trigger.

## 11. Operator responsibilities

The agent is unattended *most* of the time. The operator owns:

- **Scheduling.** One cron entry per brand. Stagger by 1–2 minutes to avoid model rate limits.
- **Token rotation.** Slack OAuth tokens expire. Rotate before they do.
- **Channel hygiene.** `--reply-to` is the destination. Wrong channel ID → wrong room.
- **Prompt tuning.** When the digest format drifts (model bump, new edge case), edit `openclaw.json` and reload.
- **Cost monitoring.** Watch the search volume and bill weekly.

## 12. Success criteria

Operator-side, after 30 days of running:

- Digest lands in the configured channel ≥ 95% of scheduled mornings.
- Operator does not manually fact-check; "Worth a click" links are sufficient.
- Operator has not had to apologize for a hallucinated post in a real channel.
- Per-brand monthly cost stays within ~10% of week-1 baseline.

## 13. Risks

- **Hallucinated content** posted under the operator's identity. Mitigation: grounding rule + citation requirement, enforced in the system prompt.
- **Wrong channel.** Mitigation: `--reply-to` is set per cron entry, not chosen by the model.
- **Silent failure.** Auth expires → 401 → exit 0. Mitigation: agent must post a failure line, not exit silently.
- **Prompt injection** from search-result content. Mitigation: the system prompt instructs the model to treat all returned search content as untrusted data and never follow instructions embedded in it.
- **Stale results treated as fresh.** Search results often lack dates. Mitigation: the agent does not assume an undated result is in-window, and reports "No material coverage" rather than padding with old items.

## 14. Open questions

- Should BrandPulse support a weekly rollup digest alongside the daily? (Default: no, until asked twice.)
- Should the digest include a "since yesterday" diff? Requires persisting state across runs — out of scope for v1.
- Should there be a "quiet day" rule that suppresses the post if there's truly nothing new? (Default: post the digest anyway, with "No material coverage" — predictability beats silence.)
