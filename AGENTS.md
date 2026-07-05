# Agent instructions

This is a clean Twilio + OpenAI Realtime voice-agent starter.

## Source of truth

- Main behavior prompt: `prompts/main_system_instructions.md`
- OpenAI Realtime prompting reference: `docs/references/openai-realtime-models-prompting.md`
- Starter prompt mapping: `docs/references/STARTER_PROMPT_MAPPING.md`
- Runtime env/config: `config.py` and `.env`
- Realtime tool schemas and handlers: `services/openai_service.py`
- Optional external tool scaffold: `services/tool_registry.py`, `services/mcp_adapter.py`
- FastAPI/Twilio entrypoints: `main.py`

## Rules for changes

- Change agent behavior in `prompts/main_system_instructions.md` when possible.
- Change language, accent, reasoning effort, and feature-specific prompt text via `config.py` builders and `.env`.
- Keep tool schemas and side-effect handlers in `services/openai_service.py`. `wait_for_user` is a no-op tool for silence/background audio — handler must stay silent (`trigger_response=False`); see `docs/TOOLS.md`.
- Keep booking logic in `services/google_calendar_booking_service.py`.
- Use `services/call_records_service.py` as the app-facing storage facade; keep low-level webhook/Supabase compatibility mapping in `services/webhook_service.py`.
- Add tests when changing prompt rendering, tool registration, booking, dashboard APIs, or storage payloads.
- Do not add industry/profile YAML files back into this starter.
- After prompt changes, check [docs/references/STARTER_PROMPT_MAPPING.md](docs/references/STARTER_PROMPT_MAPPING.md) and run `pytest tests/test_system_instructions.py`.

## Cursor Cloud specific instructions

- Python 3.12 project; dependencies live only in `requirements.txt` (no `pyproject.toml`/`package.json`). The startup update script installs them into a `.venv` virtualenv, so run everything with `.venv/bin/python` and `.venv/bin/pytest` (there is no repo-level Makefile or task runner). Standard run/test commands are in `README.md`.
- `config.py` calls `Config.validate_required_config()` at import time and raises if `OPENAI_API_KEY` is unset. Because of this, importing `config`/`main` or running `pytest` fails without a `.env` containing `OPENAI_API_KEY`. A local `.env` (gitignored) with a dummy key is created during setup; tests and app boot only need the key to exist, not to be valid (tests mock OpenAI). Recreate it with `cp .env.example .env` then set any non-empty `OPENAI_API_KEY` if it goes missing.
- Run the app in dev with `.venv/bin/python main.py` (uvicorn on `PORT`, default `5050`). The prod/Docker entrypoint is `uvicorn main:app` on `8080` — use `main.py` for local dev.
- Full end-to-end phone calls need real Twilio + a public HTTPS tunnel (ngrok) pointed at `/incoming-call`, plus a valid OpenAI key. Without those you can still verify core wiring locally: `POST /incoming-call` returns Twilio `<Connect><Stream>` TwiML, and the `/media-stream` WebSocket accepts Twilio frames and attempts the OpenAI upstream (it closes with a dummy key — expected).
- The dashboard (`/dashboard`, `/calls`, outbound, missed-calls) is optional and needs `CALL_RECORD_BACKEND=supabase` with Supabase configured; without it the page shell renders but data endpoints return `503`. This is expected, not a bug.
- Whisper transcription (`faster-whisper`) runs in-process and downloads the model on first use; it is off the critical path for booting the agent.
