# LifeCFO AI mobile app

An Expo (React Native) app for iOS and Android with the same five views as the
Streamlit app: Cash flow, Personal CFO, AI CFO chat, Rewards, and Sandbox. It
holds no financial logic: every number comes from the Python engines through
the HTTP API in `lifecfo/api/`.

## Run it on a phone (demo)

Needs Node.js 22 (the version CI uses) and the Python setup from the main
README.

1. Start the API on your computer, reachable from the local network:

   ```bash
   uv sync
   uv run uvicorn lifecfo.api.main:app --host 0.0.0.0 --port 8000
   ```

2. Start the app:

   ```bash
   cd mobile
   npm ci
   npx expo start
   ```

3. Install **Expo Go** on the phone, connect it to the same Wi-Fi, and scan the
   QR code shown in the terminal.

The app assumes the API runs on the same computer as the Expo dev server, port
8000. If it cannot connect, tap the gear icon and enter the computer's local IP
address, for example `http://192.168.1.20:8000`.

To try it in a browser instead: `npx expo start --web`.

## Configuration

| Setting | Where | Purpose |
| --- | --- | --- |
| `EXPO_PUBLIC_API_URL` | env when starting Expo | API address, for a deployed API |
| `EXPO_PUBLIC_API_TOKEN` | env when starting Expo | sent as `Authorization: Bearer` |
| `LIFECFO_API_TOKEN` | env when starting the API | if set, the API requires that token |
| `LIFECFO_DB_PATH` | env when starting the API | sandbox SQLite file (default `.lifecfo/sandbox.db`) |
| `LIFECFO_LLM_PROVIDER` | `.env` or env for the API | same AI provider settings as the web app |

The address and token can also be changed in the app (gear icon); they are kept
on the device.

## Safety rules (same as the web app)

- Approve, Reject, and Execute are only sent when the user taps them. The chat
  agent runs as `AGENT` and the sandbox refuses decisions from it.
- The app never sends a plan. It sends a strategy name, and the server
  regenerates and validates the plan from the stored state.
- What-if changes are simulated on a copy by the server and never saved.
- The API is a single-user demo server for synthetic data. Set
  `LIFECFO_API_TOKEN` if it is reachable by anyone else.

## Checks

```bash
npm run typecheck
npm run export:web   # bundles the app, catches import errors
```

## Building store apps

Use EAS (`npx eas-cli@latest build`). Not needed for the competition demo:
Expo Go is enough.
