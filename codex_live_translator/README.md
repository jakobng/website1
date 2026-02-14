# Field Translator (Android-first)

Real-time-ish field translation system for documentary/film shoots.

- Input: phone mic or external wireless receiver into phone.
- Pipeline: rolling audio chunks -> transcript -> JA/ZH to EN translation.
- Output: large live captions + rolling session log.
- Export: JSON / CSV / SRT.

## What is implemented

- FastAPI backend with APIs:
  - `POST /v1/session/start`
  - `POST /v1/realtime/connect`
  - `POST /v1/segment/process`
  - `POST /v1/text/translate`
  - `POST /v1/session/end`
  - `GET /v1/session/{id}/export?format=json|csv|srt`
- SQLite persistence for sessions and segments.
- Provider abstraction:
  - `mock` (default, no external API needed)
  - `openai` (real transcription + translation via API)
- Android-friendly web UI (`/`) with:
  - one-tap start/stop
  - source language `Auto detect` by default (manual hint optional)
  - optional conversation context box (topic hints for better translation choices)
  - mode-based capture:
    - `Realtime WebRTC (OpenAI)`: true low-latency live transcription path (finalized transcript lines translated via backend)
    - `Lower Latency`: 5s chunks
    - `Balanced`: 8s chunks
    - `Higher Accuracy`: 12s chunks
  - live translated caption
  - rolling session log
  - export buttons

## Quick start

### 1) Install deps

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2) Configure (optional)

Create `backend/.env` from example:

```powershell
Copy-Item .env.example .env
```

Default is `FT_PROVIDER=mock` so it runs immediately.

### 3) Run server

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4) Open on Android

- Phone and laptop on same network.
- Open `http://<your-computer-ip>:8000/` in Chrome on Android.
- Tap **Start Session**.

### 5) Install on Android home screen (app-like)

- Open the app URL in Chrome on Android.
- Wait a few seconds for the install prompt, then tap **Install App** in the UI.
- If Chrome shows its own prompt, accept it.
- Launch from home screen like a normal app.
- If install does not appear immediately, use Chrome menu -> **Add to Home screen**.

Note: Android microphone capture may require a secure (`https`) URL depending on device/browser policy.

## True phone-only version (cloud hosted)

If you want to use the app from phone without running your laptop server each time, host this backend online.

This repo now includes `render.yaml` for easy Render deploy.

### Step-by-step (non-technical)

1. Put this folder on GitHub as a repository.
2. Create a Render account and open the dashboard.
3. Click **New +** -> **Blueprint**.
4. Select your GitHub repo and click **Apply**.
5. Wait for deploy to finish.
6. Open the generated `https://...onrender.com/health` URL and confirm you see `status: ok`.
7. Open the main app URL (`https://...onrender.com/`) on your Android phone in Chrome.
8. Tap **Install App** (or Chrome menu -> **Add to Home screen**).
9. Launch from home screen and use normally, no laptop server needed.

### Turn on real OpenAI translation in cloud

In Render service settings -> **Environment** add:

- `FT_PROVIDER=openai`
- `FT_OPENAI_API_KEY=your_key_here`
- Optional:
  - `FT_OPENAI_TRANSCRIBE_MODEL=gpt-4o-transcribe`
  - `FT_OPENAI_TRANSLATE_MODEL=gpt-4.1-mini`

Deploy once more after setting environment variables.

### Important limits to know

- `plan: free` in `render.yaml` is the lowest-cost starter path and may sleep when idle.
- This app currently uses SQLite. On many cloud setups without a persistent disk, old session/export data can be lost after restart/redeploy.
- For production reliability, use a paid always-on plan and persistent storage.

## Provider config

### Mock mode (default)

No API keys required. Useful for end-to-end UX testing.

### OpenAI mode

In `backend/.env`:

```env
FT_PROVIDER=openai
FT_OPENAI_API_KEY=your_key_here
FT_OPENAI_TRANSCRIBE_MODEL=gpt-4o-transcribe
FT_OPENAI_TRANSLATE_MODEL=gpt-4.1-mini
```

If key is missing while `openai` is selected, app falls back to mock.

Realtime WebRTC mode also requires `openai` provider with a valid key.

## Audio hookup notes (Rode Wireless Pro)

Use either:

1. USB digital path from receiver to Android (preferred).
2. 3.5mm output from receiver into Android TRRS/USB-C audio adapter.
3. Camera headphone output into Android input chain (works for rough live translation; keep headphone volume low to avoid clipping).

Avoid Bluetooth as your primary ingest if you care about stable latency.

## External monitor path (optional)

This v1 ships phone-primary UX.

External monitor option:

1. Use Android phone with USB-C video-out support.
2. Connect USB-C -> HDMI adapter to monitor (e.g., field monitor).
3. Mirror the browser UI full-screen.

No direct camera-overlay compositor is implemented in this repo.

## API request format for `/v1/segment/process`

`multipart/form-data` fields:

- `session_id` (string)
- `segment_id` (string)
- `started_at_ms` (int)
- `ended_at_ms` (int)
- `prior_context_json` (JSON list string, optional)
- `source_lang_hint` (string, optional)
- `target_lang` (string, optional)
- `audio_file` (file)

## API request format for `/v1/realtime/connect`

`application/json` body:

- `session_id` (string)
- `offer_sdp` (string)
- `source_lang_hint` (string, optional)

Returns:

- `answer_sdp` (string)
- `call_id` (string, optional)

## API request format for `/v1/text/translate`

`application/json` body:

- `session_id` (string)
- `segment_id` (string)
- `transcript_src` (string)
- `started_at_ms` (int)
- `ended_at_ms` (int)
- `prior_context_json` (string list, optional)
- `source_lang_hint` (string, optional)
- `target_lang` (string, optional)
- `conversation_context` (string, optional)

## Tests

```powershell
cd backend
pytest -q
```

## Caveats

- Browser MediaRecorder chunk stitching is practical but not sample-accurate.
- JA/ZH accuracy depends heavily on mic quality/noise and API model behavior.
- If you need strict legal/privacy controls, add a strict-mode provider profile.

## 429 troubleshooting

If you see `429 Too Many Requests`:

1. Confirm API billing/credits are enabled for your API project.
2. Keep the default chunk cadence (now slower) or increase it further.
3. Retry after 1-2 minutes if account-level throttling was temporary.
4. Check server error text; backend now returns the provider error details.
