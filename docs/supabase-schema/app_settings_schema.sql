-- Dashboard settings override schema.
-- Run when you want dashboard Settings to persist changes in Supabase.

CREATE TABLE IF NOT EXISTS public.app_settings (
  key   text PRIMARY KEY,
  value text NOT NULL DEFAULT ''
);

COMMENT ON TABLE public.app_settings IS 'Optional runtime-safe voice-agent config overrides such as TRANSCRIPTION_MODEL, VOICE, ASSISTANT_* delivery controls, VAD, and booking settings. Do not store full prompts or industry profiles here.';
