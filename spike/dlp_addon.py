"""
Day-1 Task-1 spike addon for mitmproxy.

Goal: PROVE two things against real Claude Code traffic:
  1. We can READ the decrypted outbound prompt body (interception works).
  2. We can MODIFY it before it leaves the machine (redaction insertion point works).

Run:  mitmdump -s dlp_addon.py --listen-port 8443
(then point Claude Code at the proxy in another terminal -- see spike/README.md)
"""
import json

# The AI API hosts we care about intercepting.
AI_HOSTS = {
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.openai.com",
    "api.fireworks.ai",
}

# A fake secret to type into Claude Code so we can prove read + rewrite end-to-end.
# Send a message like: "my api key is SPIKE_SECRET_123, summarise it"
CANARY = "SPIKE_SECRET_123"
REDACTED = "[REDACTED_SECRET]"


def request(flow):
    host = flow.request.pretty_host
    if host not in AI_HOSTS:
        return

    body = flow.request.get_text()  # <-- decrypted. If this prints, MITM works.

    print("\n" + "=" * 70)
    print(f"INTERCEPTED  {flow.request.method}  https://{host}{flow.request.path}")
    print("-" * 70)

    # Pretty-print the JSON so you can eyeball the prompt the tool is sending.
    try:
        parsed = json.loads(body)
        print(json.dumps(parsed, indent=2)[:2000])
    except Exception:
        print(body[:2000])

    # PROOF OF REDACTION: rewrite the canary before forwarding.
    if CANARY in body:
        print("\n>>> Found canary in outbound body. Rewriting before it leaves the machine.")
        flow.request.set_text(body.replace(CANARY, REDACTED))
        print(">>> Rewrite applied. The real API will receive:", REDACTED)

    print("=" * 70 + "\n")
