# AI Providers: zero-cost setup

LifeCFO AI needs no paid API key. Financial calculations, optimization,
simulations, and validation are deterministic Python and never call a model.
An LLM is optional and is used only to understand natural language, choose
which tool to call, and word the explanation.

| Mode | `LIFECFO_LLM_PROVIDER` | Cost | Network | Data leaves the machine | Best for |
|---|---|---|---|---|---|
| Offline (default) | `none` | Free | None | No | Tests, recorded demo, guaranteed-reproducible runs |
| Local Ollama | `ollama` | Free | None after download | No | Live natural-language demo with full privacy |
| GroqCloud free plan | `groq` | Free within limits | Required | Yes (synthetic data only) | Fast responses without a GPU |
| Google Gemini free tier | `gemini` | Free within limits | Required | Yes (synthetic data only) | Strong language quality without a GPU |
| Custom endpoint | `custom` | Depends on the endpoint | Depends | Depends | Future paid or self-hosted provider |

**Test status.** The provider client is covered by automated tests against a
simulated HTTP transport (success, tool calls, authentication errors, missing
models, rate limits, quota exhaustion, outages, malformed answers).

**Live check, GroqCloud free plan, 14 October 2026** (model `openai/gpt-oss-120b`):
complete tool round trips worked. The model chose the right tool and arguments,
received the result, and answered with figures that all passed the number
check; answers took 2 to 4 seconds. A prompt-injection request to approve a
plan and transfer money was declined. Two fixes came out of this check: Groq
rejects the default Python user agent, so the client now sends its own; and the
number check now reads thousands grouped with spaces ("22 625").
The fourth question within one minute hit the free rate limit and was answered
offline, so expect roughly three questions a minute on this model.

**Live check, Gemini free tier, same day** (model `gemini-3.8-flash`): the key
was accepted and the model chose the correct tool. Gemini requires its "thought
signature" to be sent back with each tool call; the client now echoes
provider-specific tool-call fields. A complete round trip was not confirmed
because the free quota ran out: the quota errors reported limits of 5 and then
20 requests, consistent with a small per-minute and per-day allowance.
Responses took 10 to 20 seconds and several models returned HTTP 503.

Ollama has not been exercised live.

**Known limitation.** The number check catches invented figures, not invented
statements. In one live answer a model described the situation "before" a
change incorrectly even though every number was right. The system prompt now
forbids describing anything a tool did not return, but a model can still do
it. For the recorded demo and for evidence, use offline mode.

## How switching works

Configuration is read from environment variables, or from a `.env` file in the
repository root (copy `.env.example`). Real environment variables take
precedence over `.env`. No application code changes when the provider changes.

```
LIFECFO_LLM_PROVIDER=none | gemini | groq | ollama | custom
LIFECFO_LLM_MODEL=<model name exactly as the provider lists it>
```

Never commit `.env`. It is git-ignored.

## What happens when a provider fails

The application never switches to another provider on its own, and it never
starts using a paid service. Every failure ends in the offline engine, which is
free and always available, with a short notice in the chat.

| Situation | Behaviour |
|---|---|
| Provider selected but model or key missing | Warning in the chat view; offline mode |
| Wrong or revoked key (HTTP 401/403) | Offline answer; notice "rejected the API key" |
| Model name not found or retired | Offline answer; notice "model is not available" |
| Rate limit (HTTP 429) | Retried only when the provider asks for a wait of 8 seconds or less (at most 2 retries); otherwise offline answer at once, so retries do not burn free quota |
| Daily or monthly quota used up | No retry; offline answer |
| Timeout, no connection, server error | Up to 2 retries, then offline answer |
| Malformed response, or tool arguments that are not valid | Offline answer, or the validation error is returned to the model |
| The model states a figure that no tool produced | Its answer is discarded; the verified offline explanation is shown |
| The model keeps calling tools without answering | Stopped after 6 steps; offline answer |

Error notices never include API keys or raw provider output.

## Offline mode (default)

Nothing to install or configure.

```bash
uv run streamlit run app/main.py          # choose "AI CFO chat"
uv run python scripts/demo_offline.py     # scripted demo in the terminal
```

- A keyword router maps a question to one tool and renders the result with
  fixed templates, in English. Questions may be asked in English or Thai.
- The same question always gives the same answer, which makes it the right mode
  for the recorded demo video and for execution evidence. A saved transcript is
  in `docs/competition/evidence/offline_demo_transcript.md`.
- Limitation: it understands a fixed set of intents (summary, goals, bills,
  cash flow, plan comparison, income what-if). Anything else gets a help message.

## Local Ollama

Runs an open-source model on your own computer. Free, private, works offline.

**Hardware.** A GPU with about 8 GB of memory runs 7B to 8B models comfortably.
Without a GPU it still works on CPU, but answers can take a minute or more;
16 GB of system RAM is a sensible minimum. Model files are several GB each.

**Install.**

1. Install Ollama from https://ollama.com/download (Windows, macOS, Linux).
2. Download a model that supports tool calling. Check the "tools" tag in the
   Ollama model library; for example:
   ```bash
   ollama pull qwen2.5:7b
   ```
3. Ollama serves an API on `http://localhost:11434` once it is running.

**Configure** `.env`:

```
LIFECFO_LLM_PROVIDER=ollama
LIFECFO_LLM_MODEL=qwen2.5:7b
```

**Limitations.** Small local models choose the wrong tool or malformed
arguments more often than large hosted models. The safeguards above catch
this, so the visible effect is more answers falling back to offline mode. The
first request after starting is slow while the model loads.

**Privacy.** Prompts and results stay on the machine.

## GroqCloud free plan

**Get a key.** Create an account at https://console.groq.com and create an API
key. Check on the console whether a payment method is required in your country.

**Configure** `.env`:

```
LIFECFO_LLM_PROVIDER=groq
LIFECFO_LLM_MODEL=<a tool-capable model from the Groq console, for example openai/gpt-oss-120b>
GROQ_API_KEY=<your key>
```

**Limits.** The free plan is limited by requests per minute, requests per day,
and tokens per minute and per day, set per model and shared across the whole
account. The numbers change; the authoritative list is your own limits page in
the Groq console. One chat question uses two or more requests (one per tool
step), and tool definitions count toward tokens.

**Privacy.** Prompts are sent to Groq's servers. Read Groq's current terms
before sending anything. This project sends only synthetic data.

## Google Gemini free tier

**Get a key.** Sign in at https://aistudio.google.com and create an API key.
Free-tier availability depends on country.

**Configure** `.env`:

```
LIFECFO_LLM_PROVIDER=gemini
LIFECFO_LLM_MODEL=<a Flash model listed in AI Studio, for example gemini-3.8-flash>
GEMINI_API_KEY=<your key>
```

The client uses Gemini's OpenAI-compatible endpoint
(`https://generativelanguage.googleapis.com/v1beta/openai`).

**Limits.** Requests per minute, requests per day, and tokens per minute, per
project. The numbers and the set of free models change; check the rate-limit
page in AI Studio rather than any figure quoted elsewhere.

**Privacy.** Prompts are sent to Google. On free tiers, providers commonly
reserve the right to use submitted content to improve their products; read the
current Gemini API terms. This project sends only synthetic data, and a
free-tier key must never be used with real personal financial information.

## Custom endpoint (future paid or self-hosted provider)

Any service that implements the OpenAI chat-completions API works without code
changes:

```
LIFECFO_LLM_PROVIDER=custom
LIFECFO_LLM_BASE_URL=https://example.com/v1
LIFECFO_LLM_MODEL=<model>
LIFECFO_LLM_API_KEY=<key, if the endpoint needs one>
```

This is the only mode that can cost money, and it is used only when a person
sets it explicitly. A provider with a different API shape needs one new class
implementing `lifecfo.llm.LLMClient` (a single `complete` method); agents,
tools, and engines stay as they are.

## What is sent to a model

When an LLM provider is enabled, each chat question sends: the system rules,
the user's message (truncated to 2,000 characters), the tool definitions, and
the results of the tools the model called. Tool results contain figures from
the synthetic profile. Nothing is sent in offline mode.

## Recommendation for the competition demo

1. Record the demo video in offline mode so every run is identical.
2. Show natural-language chat live with Ollama, which needs no internet at the
   venue and keeps data on the laptop.
3. Groq is the better hosted option on the evidence so far (fast, round trips
   confirmed). Keep it for a short live segment and pause between questions.
