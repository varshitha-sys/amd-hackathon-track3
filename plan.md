# AI DLP Platform — Plan (3-Day Hackathon Sprint)

> **Hackathon:** AMD Developer Hackathon: ACT II — Track 3 (Unicorn)
> **Deadline:** July 11, 2026
> **Team Size:** 5 people
> **Start Date:** July 9, 2026

---

## Feasibility Assessment: Plugin for Claude Code, Antigravity & OpenClaw

### TL;DR — Feasible, but the proxy is the hard part. De-risk it first.

All three tools respect standard proxy environment variables, so you don't need a
custom plugin per tool. **But there's a critical nuance the first draft of this plan
got wrong:** setting `HTTPS_PROXY` alone only routes an *encrypted TLS tunnel* through
your proxy — you cannot read or redact the prompt body from it.

To actually inspect and modify the request body, you must perform **TLS
man-in-the-middle (MITM)**: run your own Certificate Authority (CA) and make each
client *trust that CA*. This is well-trodden (mitmproxy does exactly this for Claude
Code) but it is **not a one-liner and not "easy."** Treat it as your highest-risk
component.

| Tool | Interception Method | What's actually required | Difficulty |
|------|---------------------|--------------------------|------------|
| **Claude Code** | `HTTPS_PROXY` + TLS MITM | `HTTPS_PROXY=http://localhost:8443` **AND** `NODE_EXTRA_CA_CERTS=/path/to/dlp-ca.pem`. Without the CA var, Node's TLS layer rejects your cert and **Claude Code fails silently.** | Medium — documented, but the CA step is mandatory |
| **Antigravity** (`agy`) | `HTTPS_PROXY` + TLS MITM | Same as Claude Code (Node-based → uses `NODE_EXTRA_CA_CERTS`). Also supports MCP servers for deeper integration. **Verify proxy+CA behavior day-of.** | Medium |
| **OpenClaw** | `HTTPS_PROXY` + CA **OR** native `message_sending` hook | Proxy path needs CA trust like the others. The native `message_sending` hook (`openclaw hooks`) can intercept/modify/block a message *before send* with no TLS at all — cleaner but tool-specific. | Easy (hook) to Medium (proxy) |

### The Architecture: Local DLP Proxy

You build **one component** — a local HTTPS MITM proxy that:

1. Runs on `localhost:8443` with its own CA cert (`dlp-ca.pem`)
2. Terminates TLS for requests to known AI API endpoints (`api.anthropic.com`,
   `generativelanguage.googleapis.com`, `api.openai.com`, `api.fireworks.ai`, etc.)
3. Extracts the prompt/message body from the decrypted request
4. Runs **Tier 1** (regex PII detection) locally — always
5. Runs **Tier 2** (AMD-hosted Gemma classifier) **only when Tier 1 or a heuristic
   flags something** — avoids an LLM round-trip on every single message (see Latency
   note below)
6. Acts on the sensitivity label (`INFO` / `WARN` / `ACTION_NEEDED` / `BLOCK`):
   - `INFO` / `WARN`: Log and forward (optionally with redaction)
   - `ACTION_NEEDED`: Redact sensitive tokens, forward the sanitized request
   - `BLOCK`: Return an error response, do NOT forward
7. Re-encrypts and forwards to the real endpoint

**Correct user setup (per tool — the CA cert is not optional):**
```bash
# 1. Trust the DLP CA (one time)
export HTTPS_PROXY=http://localhost:8443
export NODE_EXTRA_CA_CERTS=$HOME/.ai-dlp/certs/dlp-ca.pem   # Claude Code, Antigravity (Node)

# 2. Then use any tool normally
claude
agy
openclaw chat   # or: register the native message_sending hook instead
```
```powershell
# Windows PowerShell
$env:HTTPS_PROXY = "http://localhost:8443"
$env:NODE_EXTRA_CA_CERTS = "$HOME\.ai-dlp\certs\dlp-ca.pem"
```

> ⚠️ **Do not ship the plan's old "just `export HTTPS_PROXY`" instruction** — it makes
> Node-based tools fail silently.

### ⚠️ The trust question (have an answer ready for judges)

A DLP tool that MITMs all your AI traffic is decrypting your prompts **and your API
keys**. A judge *will* ask "why should I trust this?" Your answer:

- Runs **100% locally** — decrypted traffic never leaves the machine
- **Open source** — the CA and interception logic are auditable
- **Keys never stored or logged** — you already hash the original text (see logging);
  API keys are pass-through only and never persisted
- The CA is **user-generated on their own machine**, not a shared/embedded key

### ⏱️ Latency note

An LLM round-trip to Fireworks sits in the *request path* of every intercepted
message. "~100–200ms" is optimistic — expect **400ms–1.5s**. Mitigation: run Tier 2
**only when Tier 1 or a cheap heuristic flags the message**, and cache classifications
for identical/similar inputs. Never classify every keystroke.

---

## Project Structure (Monorepo)

```
ai-dlp-platform/
├── proxy/                    # Local HTTPS/TLS MITM proxy server (Node.js)
│   ├── src/
│   │   ├── server.js         # Proxy server entry point
│   │   ├── interceptor.js    # Request body extraction & routing
│   │   ├── tier1.js          # Regex-based PII detection engine
│   │   ├── tier2.js          # Fireworks AI / Gemma API client (flagged-only)
│   │   ├── redactor.js       # Smart token redaction logic
│   │   └── logger.js         # Audit trail logging
│   ├── certs/                # DLP CA for TLS interception (dlp-ca.pem)
│   ├── package.json
│   └── Dockerfile
│
├── extension/                # Chrome browser extension (SAFE HERO DEMO)
│   ├── manifest.json         # Manifest V3
│   ├── content.js            # Content script (intercepts chat inputs, no TLS needed)
│   ├── background.js         # Service worker (API calls to backend)
│   ├── popup.html/js/css     # Extension popup UI
│   └── icons/
│
├── backend/                  # Classification API server (Python/FastAPI)
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── classifier.py     # Gemma inference (Fireworks AI or AMD Dev Cloud)
│   │   ├── patterns.py       # PII regex patterns library
│   │   ├── redactor.py       # Redaction engine
│   │   ├── session.py        # Conversation-level running risk score
│   │   └── models.py         # Request/response schemas
│   ├── requirements.txt
│   └── Dockerfile
│
├── dashboard/                # Compliance dashboard (simple web UI)
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── openclaw-hook/            # (Stretch) Native OpenClaw message_sending hook
│   └── message_filter.js
│
├── docker-compose.yml        # Full stack orchestration
├── setup.sh                  # One-command setup (generates CA, sets env vars)
└── README.md
```

---

## 3-Day Task Breakdown

### Day 1 — July 9 (Wednesday): De-risk the proxy, then build the core engine

**Goal:** Prove the make-or-break thing (TLS MITM against real Claude Code) works
*first*, then get the detection engine working end-to-end.

> **Sequencing rule:** Task 1 is a time-boxed spike. If TLS MITM isn't working against
> real Claude Code traffic by ~1pm, escalate — make the **browser extension the hero
> demo** (it needs no TLS MITM) and treat the proxy as a stretch. Know this at 1pm Day
> 1, not 6pm Day 2.

| # | Task | Details | Est. Time |
|---|------|---------|-----------|
| 1 | **🔴 SPIKE: TLS MITM proxy vs. real Claude Code** | **Do this before anything else.** Stand up a minimal MITM proxy (e.g. `http-mitm-proxy` / mitmproxy), generate `dlp-ca.pem`, set `HTTPS_PROXY` **+ `NODE_EXTRA_CA_CERTS`**, run Claude Code, and confirm you can read the decrypted request body to `api.anthropic.com`. Success = you print an outbound prompt. Failure by ~1pm → pivot hero demo to the extension. | 2-3 hours (time-boxed) |
| 2 | **Project scaffolding** | Initialize monorepo, set up `proxy/`, `backend/`, `extension/`, `dashboard/`. Init `package.json`, `requirements.txt`, basic Dockerfiles. | 1 hour |
| 3 | **Tier 1: Regex PII detection engine** | Build `patterns.py` / `tier1.js`: Aadhaar, PAN, Indian phone numbers, SSNs, credit cards, emails, IPs, API keys/secrets (AWS, GCP, GitHub tokens), plaintext passwords, URLs with auth tokens. Test with sample inputs. | 2-3 hours |
| 4 | **Tier 2: Gemma classification (Fireworks AI)** | Set up Fireworks AI client. Write a Gemma system prompt classifying text into `INFO`/`WARN`/`ACTION_NEEDED`/`BLOCK`, detecting: org-specific terms, project codenames, internal infra, government credential patterns. Few-shot examples in the prompt. Test with nuanced cases regex misses. | 2-3 hours |
| 5 | **Backend API server (FastAPI)** | Build `/classify`: takes a prompt string, runs Tier 1 always + Tier 2 **only if flagged**, returns detected entities, sensitivity label, redacted text, confidence, tier. | 2-3 hours |
| 6 | **Wire proxy → backend** | Extend the Day-1 spike proxy to call the backend `/classify` and act on the label (forward / redact-and-forward / block). | 2-3 hours |
| 7 | **Test end-to-end with Claude Code** | With proxy + backend running, type a PII prompt in Claude Code, verify it's caught, redacted, or blocked. | 1 hour |

**Day 1 Deliverable:** Proxy + backend catching PII in Claude Code prompts — **or**, if
the spike failed, a green light to pivot to the extension as hero and a clear record of
why.

---

### Day 2 — July 10 (Thursday): Hero demo (extension), dashboard, real AMD story

**Goal:** Browser extension working on ChatGPT/Claude/Gemini as the reliable hero demo.
Basic dashboard showing logs. Conversation-level scoring made *real* (not faked). If
the proxy spike succeeded early, deploy Gemma on AMD Developer Cloud for a defensible
AMD story.

| # | Task | Details | Est. Time |
|---|------|---------|-----------|
| 8 | **Chrome extension — content script (HERO DEMO)** | Manifest V3. Content script hooks textarea/input on `chat.openai.com`, `claude.ai`, `gemini.google.com`, reads text before submit, calls `/classify`, shows inline overlay with the label. `ACTION_NEEDED` → redacted preview + confirm. `BLOCK` → prevent submission + alert. **This needs no TLS MITM — it's your most reliable stage demo.** | 4-5 hours |
| 9 | **Chrome extension — popup UI** | Protection on/off toggle, recent interceptions count, link to dashboard. | 1-2 hours |
| 10 | **Backend: session-level running risk score** | Implement `session.py`: keep a per-session buffer, re-score the *running thread* so cumulative context bumps the label even when each message looks benign. Keep it minimal but **real** — this is the headline differentiator; do not hardcode it. | 2-3 hours |
| 11 | **Compliance dashboard** | Single page: real-time log of intercepted prompts (timestamp, tool, label, snippet), label-distribution chart, filterable table. Source: backend `/logs` + `/stats`. | 3-4 hours |
| 12 | **Backend: logging & audit trail** | SQLite logging: timestamp, source (proxy/extension), original-text **hash** (never raw), detected entities, label, action. Expose `/logs` and `/stats`. | 2-3 hours |
| 13 | **(If proxy spike succeeded early) Deploy Gemma on AMD Developer Cloud** | Stand up the classifier on an MI300X instance via vLLM/ROCm so the AMD story is "we ran inference on MI300X," not "we called an API that happens to use AMD." Fall back to Fireworks if time runs out. | 2-4 hours |
| 14 | **Test with Antigravity & OpenClaw** | Verify proxy interception (`HTTPS_PROXY` **+ CA**) works with `agy` and `openclaw`; try the native OpenClaw `message_sending` hook. Document quirks. | 1-2 hours |
| 15 | **Smart redaction refinement** | Named placeholders: `[REDACTED_EMAIL]`, `[REDACTED_IP]`, `[REDACTED_CREDENTIAL]`, etc. Keep the redacted prompt useful to the model. | 1-2 hours |

**Day 2 Deliverable:** Extension (hero) + dashboard working; conversation-level scoring
real; proxy working across CLI tools; AMD inference story firmed up.

---

### Day 3 — July 11 (Friday): Containerize, Demo & Submit

**Goal:** Containerize everything. Record a killer demo video. Write docs. Submit.

| # | Task | Details | Est. Time |
|---|------|---------|-----------|
| 16 | **Containerization** | `docker-compose.yml` spinning up backend, dashboard, proxy. One-command startup: `docker-compose up`. | 2-3 hours |
| 17 | **README & documentation** | Problem, architecture diagram, **correct** setup instructions (incl. `NODE_EXTRA_CA_CERTS`), screenshots, tech stack, **AMD infrastructure usage** (be specific — see below). | 1-2 hours |
| 18 | **Setup script** | `setup.sh` / `setup.ps1`: install deps, **generate the DLP CA**, set `HTTPS_PROXY` + `NODE_EXTRA_CA_CERTS`, start all services. | 1 hour |
| 19 | **Demo video (max 5 min)** | (1) Problem 30s, (2) Architecture 30s, (3) **Hero: extension catching PII on ChatGPT 1 min**, (4) Proxy catching PII in Claude Code 1 min, (5) Dashboard audit trail 30s, (6) **AMD usage** 30s, (7) Startup vision / market 1 min. | 2-3 hours |
| 20 | **Slide deck (PDF)** | 10-12 slides: problem, solution, architecture, demo screenshots, tech stack, **AMD usage**, "why trust our proxy," market/TAM, team. | 1-2 hours |
| 21 | **Final testing & bug fixes** | End-to-end smoke test. Fix breakers. | 1-2 hours |
| 22 | **Submit on lablab.ai** | GitHub repo, demo video (MP4), slide deck (PDF), cover image, live demo URL (if deployed), 100+ word description. | 30 min |

**Day 3 Deliverable:** Submitted project with demo video, slides, containerized repo,
and documentation.

---

## What to Prioritize If Time Is Short

Cut ruthlessly. Priority order:

| Priority | Component | Why |
|----------|-----------|-----|
| **P0 (Must Have)** | Backend API with Tier 1 + Tier 2 detection | This IS the product |
| **P0 (Must Have)** | **Browser extension (hero demo)** | Reliable on stage, no TLS MITM, visual and impressive |
| **P0 (Must Have)** | Demo video + slides | You literally cannot win without these |
| **P1 (Should Have)** | Local DLP proxy (Claude Code first) | Your true differentiator — but higher risk; Claude Code is the safe target |
| **P1 (Should Have)** | **Conversation-level risk scoring (real, minimal)** | Your headline differentiator — build a real minimal version, do NOT fake it |
| **P1 (Should Have)** | Docker containerization | Submission requirement |
| **P2 (Nice to Have)** | Gemma deployed on AMD Developer Cloud | Strongest AMD story; Fireworks is the fallback |
| **P2 (Nice to Have)** | Compliance dashboard | Great in demo but can be simple |
| **P3 (Stretch)** | Proxy across all 3 CLI tools + OpenClaw native hook | Claude Code alone is enough to prove the concept |

> **Change from the previous plan:** conversation-level scoring moved from "P3, fake
> it" up to **P1, build it real** — it's the differentiator you lead with, and judges
> ask follow-ups. The proxy moved from P0 to **P1** because the extension is the safer
> hero demo; the proxy is the "wow, it even works in your terminal" moment, not the
> thing the whole demo rests on.

---

## Tech Stack Summary

| Component | Technology | Why |
|-----------|------------|-----|
| Backend API | Python + FastAPI | Fast to build, great for ML/AI integration |
| PII Detection (Tier 1) | Regex (Python `re`) | Fast, no dependencies, runs locally |
| AI Classification (Tier 2) | Gemma via Fireworks AI (AMD MI300X) — or self-hosted on AMD Dev Cloud | Uses AMD MI300X for inference |
| Local Proxy | Node.js (`http-mitm-proxy` or `mitmproxy`) | Mature TLS-MITM interception libraries |
| Browser Extension | Vanilla JS + Chrome Manifest V3 | No framework needed for hackathon scope |
| Dashboard | HTML + CSS + Vanilla JS | Simple, no build step, serves from backend |
| Database | SQLite | Zero config, file-based, good enough for demo |
| Containerization | Docker + docker-compose | Submission requirement |
| AMD Infrastructure | AMD Developer Cloud (MI300X) + Fireworks AI | Hackathon requirement |

---

## Key API Endpoints (Backend)

```
POST /api/classify
  Input:  { "text": "...", "source": "proxy|extension", "session_id": "...", "context": [...] }
  Output: {
    "label": "WARN",
    "entities": [
      { "type": "EMAIL", "value": "john@gov.in", "start": 45, "end": 57 }
    ],
    "redacted_text": "... [REDACTED_EMAIL] ...",
    "confidence": 0.92,
    "tier": "tier2",
    "session_risk": 0.71
  }

GET  /api/logs?limit=50&label=BLOCK
  Output: [ { "timestamp": "...", "source": "...", "label": "...", ... } ]

GET  /api/stats
  Output: { "total": 142, "by_label": { "INFO": 80, "WARN": 35, ... } }
```

---

## How AMD Infrastructure Is Used (Important for Judging)

Make this crystal clear — and **avoid fluff**. AMD engineers are judging; vague
"memory bandwidth" claims get seen through.

1. **Gemma inference on AMD Instinct MI300X** — Tier 2 contextual classification runs
   on Gemma served on MI300X, either via **Fireworks AI (production-verified AMD MI300X
   partner)** or self-hosted on **AMD Developer Cloud** with vLLM/ROCm. If you deploy
   yourself, say so — "we ran inference on MI300X with ROCm" is far stronger than "we
   called an API."
2. **AMD Developer Cloud** — Used for model experimentation, latency benchmarking, and
   classification-accuracy testing on MI300X instances.
3. **ROCm** — The software stack for any self-hosted inference / custom model work on
   AMD Developer Cloud.

> ❌ **Cut the old claim** that "MI300X memory bandwidth enables holding full
> conversation context." Any GPU/API holds a conversation in its context window — this
> is marketing, not engineering, and judges will call it out. Justify AMD usage with
> *real* inference deployment and benchmarks instead.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **TLS MITM is the make-or-break component** | **Spike it Day 1 morning (Task 1).** Use a well-tested library. Pre-generate the CA. If not working by ~1pm Day 1, pivot the hero demo to the browser extension (no TLS needed). |
| Node tools fail silently without CA trust | Always set `NODE_EXTRA_CA_CERTS` alongside `HTTPS_PROXY`. Bake it into `setup.sh` and the README. |
| Fireworks AI API rate limits | Only call Tier 2 on flagged messages. Cache identical/similar inputs. Tier 1 regex is a standalone fallback. |
| Extension content script breaks on site updates | Target stable DOM elements. Test on the specific ChatGPT/Claude/Gemini versions the day of submission. |
| "Why trust a proxy that decrypts my keys?" | Local-only, open source, keys never logged (text is hashed), user-generated CA. Put this on a slide. |
| Latency in request path | Tier-2-on-flag-only + caching. Expect 400ms–1.5s per LLM call; don't classify every message. |
| Time pressure | Follow the revised P0/P1/P2 list. Cut proxy-across-all-tools and native hooks first; keep extension + backend + real session scoring. |
| Gemma classification accuracy | Prompt-engineer Day 1 with few-shot examples. Don't fine-tune (no time) — use prompted inference. |

---

## One-Liner Pitch

> **"An AI-powered DLP shield that sits between you and your AI tools — catching
> sensitive data leaks before they leave your machine, whether you're chatting on
> ChatGPT or coding with Claude Code."**
