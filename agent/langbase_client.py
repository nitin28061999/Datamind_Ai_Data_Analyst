"""
Thin wrapper around a Langbase Pipe (a hosted, versioned prompt/agent).

This project is wired to your real pipe:
    https://langbase.com/nitin28061999/datamind-ai-analyst

A Pipe on Langbase is identified by its own API key (not a "name" field in the
request body) — you generate that key from the pipe's own settings page
("API keys" tab on the pipe's dashboard), not from your general account keys.
Endpoint and auth per Langbase's current v1 API:
    POST https://api.langbase.com/v1/pipes/run
    Authorization: Bearer <PIPE_API_KEY>
    body: {"messages": [...], "stream": false}

Why route the final answer through this pipe instead of a raw Gemini call:
- The datamind-ai-analyst pipe's system prompt is already tuned for
  interpreting tool output like a data analyst — surfacing insights,
  suggesting KPIs, drafting SQL/Python when useful — so it's a better fit
  for the "turn raw numbers into a business answer" step than a generic
  prompt would be.
- Anyone on the team can tune that system prompt from the Langbase UI
  without touching this codebase.

For the initial demo, LANGBASE_API_KEY can be left blank — every call
transparently falls back to a local Gemini prompt so the app is fully
runnable on day one. Paste in the pipe's API key to switch over with no
other code changes.
"""
import os
import requests

LANGBASE_API_KEY = os.getenv("LANGBASE_API_KEY", "")
LANGBASE_PIPE_URL = os.getenv("LANGBASE_PIPE_URL", "https://api.langbase.com/v1/pipes/run")


def run_langbase_pipe(pipe_name: str, messages: list, fallback_fn=None):
    """
    Calls the configured Langbase pipe if LANGBASE_API_KEY is set; otherwise
    (or on any failure) calls fallback_fn(messages) so the app degrades
    gracefully. `pipe_name` is used only for logging — the pipe itself is
    determined by which pipe's API key is set in LANGBASE_API_KEY.
    """
    if LANGBASE_API_KEY:
        try:
            resp = requests.post(
                LANGBASE_PIPE_URL,
                headers={
                    "Authorization": f"Bearer {LANGBASE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"messages": messages, "stream": False},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            completion = data.get("completion")
            if completion:
                return completion
            return data.get("raw", {}).get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            print(f"[Langbase] pipe '{pipe_name}' call failed, using local fallback: {e}")

    if fallback_fn:
        return fallback_fn(messages)
    raise RuntimeError(f"Langbase not configured and no fallback provided for pipe '{pipe_name}'.")
