# Public demo on Streamlit Community Cloud

The web app can run as a free public demo on
[Streamlit Community Cloud](https://share.streamlit.io). It uses synthetic data
only and needs no API key: without one, the AI CFO chat answers in offline mode.

## What the repository already provides

- Dependencies: Community Cloud installs from `uv.lock` (first in its priority
  order), which also installs the `lifecfo` package the app imports.
- Theme: `.streamlit/config.toml` at the repository root, which is where
  Community Cloud reads it.
- Per-visitor sandbox: with `LIFECFO_SANDBOX = "session"` every visitor gets a
  private in-memory sandbox. One visitor's approvals, executed plans or reset
  never appear for anyone else, and nothing is kept after the browser session
  ends. Without this setting all visitors would share one SQLite file.

## Deploy (repository owner, once)

1. Sign in at https://share.streamlit.io with the GitHub account that owns
   `prommitr27-dev/lifecfo-ai`.
2. Click **Create app**, then **Deploy a public app from GitHub**.
3. Repository `prommitr27-dev/lifecfo-ai`, branch `main`, main file path
   `app/main.py`. Pick a custom subdomain if you like, e.g. `lifecfo-ai`.
4. Open **Advanced settings**:
   - Python version: **3.12** (matches CI).
   - Secrets: paste
     ```toml
     LIFECFO_SANDBOX = "session"
     ```
     Root-level secrets are exposed to the app as environment variables.
5. Click **Deploy**. The first build takes a few minutes.

## Optional: LLM answers in the chat

Add the provider settings from [AI_PROVIDERS.md](AI_PROVIDERS.md) to the same
Secrets box (for example `LIFECFO_LLM_PROVIDER` and `GROQ_API_KEY`). Never put a
key in the repository. Anyone with the public link can then spend that key's
quota, so prefer a free-tier key with a spending limit, or stay in offline mode.

## After deploying

- Every push to `main` redeploys the app automatically.
- An app with no visitors for a while goes to sleep; the first visitor wakes it
  with one click.
