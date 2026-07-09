# Day-1 Task-1 Spike: Prove TLS MITM works against Claude Code

**Success criterion:** you send a message in Claude Code and the mitmproxy terminal
prints the decrypted prompt body — AND the canary secret gets rewritten before it
leaves the machine. If that happens, the whole DLP-proxy idea is feasible. If it
doesn't work by ~1pm, pivot the hero demo to the browser extension.

---

## Step 0 — Install mitmproxy (one time) — DONE

Already installed via `uv tool install mitmproxy` (v12.2.3). The `mitmdump`,
`mitmproxy`, and `mitmweb` commands are on your PATH (`~/.local/bin`).

## Step 1 — Start the proxy with the DLP addon (Terminal A)

```bash
cd /home/shardunya/codePractice/fullStack/amd-hackathon-track3/spike
mitmdump -s dlp_addon.py --listen-port 8443
```

First run generates the CA at `~/.mitmproxy/mitmproxy-ca-cert.pem`. Leave this running.

> Prefer a visual UI? Use `mitmweb -s dlp_addon.py --listen-port 8443`
> and watch flows at http://localhost:8081.

## Step 2 — Point Claude Code at the proxy (Terminal B)

**Both** env vars are required. `HTTPS_PROXY` alone makes Claude Code fail *silently* —
Node rejects the proxy's cert without `NODE_EXTRA_CA_CERTS`.

```bash
export HTTPS_PROXY=http://localhost:8443
export HTTP_PROXY=http://localhost:8443
export NODE_EXTRA_CA_CERTS=$HOME/.mitmproxy/mitmproxy-ca-cert.pem
claude
```

## Step 3 — Trigger traffic and confirm

In that Claude Code session, send:

```
my api key is SPIKE_SECRET_123, just say ok
```

Then look at **Terminal A**. You should see:
- `INTERCEPTED  POST  https://api.anthropic.com/v1/messages...`
- the decrypted JSON body containing your message  ✅ read works
- `>>> Rewrite applied. The real API will receive: [REDACTED_SECRET]`  ✅ modify works

If you see all three, **Task 1 passes.** You've proven interception + redaction.

---

## If it fails — triage

| Symptom | Likely cause | Fix |
|---|---|---|
| Claude Code hangs / errors on connect | CA not trusted | Confirm `NODE_EXTRA_CA_CERTS` points to the real `~/.mitmproxy/mitmproxy-ca-cert.pem` and the file exists |
| Nothing prints in Terminal A | Traffic not going through proxy | Confirm `HTTPS_PROXY` is set *in the same shell* you launched `claude` from (`echo $HTTPS_PROXY`) |
| Connects but body is unreadable/binary | host not in `AI_HOSTS`, or non-JSON | Check the printed host; add it to `AI_HOSTS` in `dlp_addon.py` |
| Works but auth fails | OAuth token stripped | You're on subscription login — the token is in headers, not body; mitmproxy passes headers through untouched, so this shouldn't happen. If it does, note it and test with an `ANTHROPIC_API_KEY` instead |

## Cleanup (important — don't leave your traffic routed through a dead proxy)

```bash
unset HTTPS_PROXY HTTP_PROXY NODE_EXTRA_CA_CERTS
```
