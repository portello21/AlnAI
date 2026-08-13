# ROG AI Family V9 — Release Candidate Gate

This document defines the final local validation before any merge to `main`.

## Automated gate

The branch must have a green `ROG AI V8/V9 Quality` workflow for its HEAD. The workflow compiles active Python sources and runs the established V8/V9 contracts. A green CI result is necessary but does not replace browser/device testing.

## Required local secrets

Keep secrets only in `.streamlit/secrets.toml` or environment variables. Never commit real values.

Required for family login and trusted-device persistence:

```toml
DEVICE_COOKIE_SECRET = "use-a-random-secret-with-at-least-32-characters"
ALLAN_PASSWORD = "..."
BEATRIZ_PASSWORD = "..."
NATAN_PASSWORD = "..."
TAINAN_PASSWORD = "..."
```

Optional integrations:

```toml
DEEPSEEK_API_KEY = "..."
NVIDIA_API_KEY = "..."
NVIDIA_MODEL = "..."
SUPABASE_URL = "..."
SUPABASE_KEY = "..."
```

Paid providers remain guarded by `ROG_ALLOW_PAID=false` unless the owner explicitly opts in.

## Local release test

Run from PowerShell:

```powershell
Set-Location "C:\Users\allan\AllanAI"
git fetch origin
git switch rog-v8-hardening
git pull --ff-only origin rog-v8-hardening
python -m py_compile .\app.py
python .\scripts\validate_v8.py
python .\scripts\validate_v9.py
streamlit run .\app.py
```

Then validate in the browser:

1. Login as Allan.
2. Send one message to Core and each specialist.
3. Reload with F5; Allan must remain authenticated when trusted-device support is configured.
4. Close and reopen the browser; the valid trusted device should restore Allan.
5. Use `Esquecer este dispositivo`; reopening must require login.
6. Login as Natan in a private/incognito window and verify that Allan/Beatriz/Tainan history, memories, documents and shared finance are not visible.
7. Login as Tainan and repeat the isolation check.
8. Login as Beatriz, use Finance, enable shared finance, and verify only the explicit finance shared scope is visible.
9. Confirm Beatriz Personal/Tech/Document does not expose Allan private information.
10. Upload a small TXT/PDF in Allan and verify Natan/Tainan cannot retrieve it.
11. Test an invalid/oversized attachment and confirm the UI fails gracefully.
12. Test audio only if Whisper/ffmpeg is installed locally.
13. Disable the local model and verify the UI does not hang.
14. With `ROG_ALLOW_PAID=false`, confirm no paid-provider-only configuration silently generates a paid call.

## Release blockers

Do not merge to `main` if any of the following occurs:

- cross-profile history, memory or document leakage;
- shared finance visible outside Allan/Beatriz Finance;
- F5 logs into the wrong profile;
- logout/forget-device does not clear authentication;
- duplicate user messages or duplicate assistant responses;
- infinite spinner or unrecoverable provider failure;
- traceback shown to normal users;
- secrets or local databases tracked by Git;
- GitHub Actions not green for the exact candidate commit.

## Rollback

The working branch is independent from `main`. Until release validation succeeds, rollback is simply switching back to the known-good production branch/commit. Do not force-push `main`.

## Validation labels

Use only these labels in release notes:

- **VALIDADO AUTOMATICAMENTE** — covered by compile/tests/CI.
- **PRECISA DE TESTE LOCAL** — depends on the real browser, Windows, secrets, Docker, GPU, microphone or external account.
