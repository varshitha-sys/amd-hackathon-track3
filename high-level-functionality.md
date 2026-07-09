# AI DLP Platform — Architecture Idea

## How AMD Fits In (The Differentiator)

The core limitation of standard DLP (Data Loss Prevention) tools is their reliance on client-side regex/pattern matching. This is fast but dumb; it only catches obvious PII (SSNs, credit card numbers, etc.). It fails to catch contextual leaks, such as internal project codenames, government infrastructure details, or gradual information exposure across a conversation.

This platform proposes a **Two-Tier Detection Architecture** leveraging AMD Instinct MI300X GPUs in the backend to enable context-aware sensitivity detection.

### Two-Tier Detection Architecture

| Tier | Location | Technology / Focus | Speed |
| :--- | :--- | :--- | :--- |
| **Tier 1 (Client-side)** | Browser extension / CLI plugin | Fast regex + pattern matching (catches SSNs, Aadhaar, credit cards, emails, API keys). | Instant (<5ms) |
| **Tier 2 (Server-side)** | AMD MI300X Cloud Backend | Contextual sensitivity classification (Gemma model serving via Fireworks AI). Catches project names, internal domains, infrastructure layouts, and cumulative leakage. | Fast (~100-200ms) |

---

## Key Features to Differentiate from the Market

### 1. Conversation-Level Risk Scoring
Instead of analyzing messages in isolation, the platform scores the **entire conversation thread** dynamically. A single prompt might seem benign, but when aggregated across a session, it could expose sensitive operational contexts. The AMD-hosted Gemma model leverages the massive memory capacity of the MI300X to evaluate multi-turn context.

### 2. Org-Specific Sensitivity Profiles
Allows enterprises and government departments to upload proprietary terms, domain names, employee directories, and server ranges. The server-side model can be fine-tuned or contextualized via RAG on AMD hardware to catch organization-specific details.

### 3. Smart Redaction (Context Preservation)
Instead of hard-blocking messages, the tool uses named entity recognition (NER) to surgically redact sensitive tokens and insert placeholder variables (e.g., `[REDACTED_HOSTNAME]`, `[REDACTED_PROJECT]`), preserving the usability of the prompt for the target LLM.

### 4. Agentic Tool Interception
Integrates with CLI/agentic developer tools (such as Claude Code, Antigravity, or OpenClaw) via a lightweight local proxy that intercepts outbound LLM API requests, redacting PII before it reaches external endpoints.

---

## Sensitivity Classification & Actions

| Label | Action Taken | Scenario Example |
| :--- | :--- | :--- |
| `INFO` | Log only; let pass | Generic organization name mentioned |
| `WARN` | Highlight banner; allow with bypass | Internal project name detected |
| `ACTION NEEDED` | Prompt user with redacted preview; require confirmation | Government credential pattern found |
| `BLOCK` | Stop prompt transmission | API keys, passwords, or highly classified document content |

---

## Comparison Matrix

| Existing DLP Solutions | Proposed AMD-Powered DLP Platform |
| :--- | :--- |
| Regex-only detection | AI-powered contextual classification |
| Message-level scanning | **Conversation-level** cumulative risk scoring |
| Generic templates | **Org-specific** fine-tuned sensitivity models |
| Block or Allow | **Smart Redaction** (preserves AI usability) |
| Web-only interfaces | Covers Web UIs **plus CLI/Agentic AI developer tools** |
