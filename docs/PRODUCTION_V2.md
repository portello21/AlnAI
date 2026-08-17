# ROG AI production v2

## Activation order

1. Keep the current Streamlit app on `main` and verify its existing secrets.
2. In Supabase Auth, decide the four private email addresses for Allan, Beatriz, Natan and Tainan. Do not commit them.
3. Set the following only in the deployment secret store:

```toml
SUPABASE_AUTH_ENABLED = "true"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
SUPABASE_SERVICE_ROLE_KEY = "sb_secret_..."
ALLAN_AUTH_EMAIL = "..."
BEATRIZ_AUTH_EMAIL = "..."
NATAN_AUTH_EMAIL = "..."
TAINAN_AUTH_EMAIL = "..."
ROG_LEGACY_AUTH_FALLBACK = "true"
```

4. In a trusted administration environment, export each password as an environment variable and run `python scripts/provision_supabase_users.py`. The script never prints passwords.
5. Confirm every migrated profile can sign in. Then set `ROG_LEGACY_AUTH_FALLBACK = "false"` and remove the legacy profile-password secrets after the final verification.

Authorization comes from `auth.users.raw_app_meta_data` and the active row in `rog_user_profiles`. User-editable metadata is never accepted for authorization.

Administrative API routes require an admin mapping and, by default, an `aal2` Supabase session (`ROG_ADMIN_REQUIRE_MFA=true`). Enroll Allan in Supabase TOTP MFA before using remote user activation controls.

## Agent API and installable client

Build `Dockerfile.api` on a private container host and configure the same provider and Supabase secrets as Streamlit. Do not pass secrets as Docker build arguments.

```powershell
docker build -f Dockerfile.api -t rog-ai-api .
docker run --rm -p 8080:8080 --env-file .env rog-ai-api
```

Health check: `GET /health`. The installable client is served at `/app/`. Authenticated agent routes are under `/v1/`; chat uses Server-Sent Events and supports cancellation. The service worker caches only the static app shell and explicitly bypasses every `/v1/` request.

## Privacy-safe observability

`SENTRY_DSN` enables scrubbed error reporting with request, user and breadcrumb data removed. `POSTHOG_API_KEY` enables a small allowlist of operational product events. Prompts, responses, documents, memories, profile names and raw user IDs are not sent. Set `OBSERVABILITY_HASH_SECRET` to a separate random secret of at least 32 characters.

## Cost and abuse controls

- `ROG_API_RATE_LIMIT_PER_MINUTE` defaults to 12 requests per authenticated user.
- `ROG_API_MAX_HISTORY_MESSAGES` defaults to 40.
- Paid providers remain disabled unless `ROG_ALLOW_PAID=true`.
- `ROG_PAID_PROVIDER_DAILY_REQUEST_LIMIT` defaults to 50 per running instance.
- Provider circuit breakers and timeouts remain active.

## Backup, restore and retention

Enable Supabase managed backups or point-in-time recovery for Auth and Postgres recovery. Application-level encrypted exports complement, but do not replace, managed backups.

Generate a Fernet key once and keep it in a backup vault:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
$env:ROG_BACKUP_ENCRYPTION_KEY = "value-from-the-vault"
python scripts/backup_supabase_data.py --output "D:\secure-backups\rog-ai.rogbackup"
```

Restores require the explicit `--confirm-restore` flag. Test restoration against a non-production project before relying on a backup. Run `core.operations_store.enforce_retention()` from a trusted scheduler; audit defaults to 90 days and usage to 180 days.
