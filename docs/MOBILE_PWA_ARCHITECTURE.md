# ROG AI mobile / PWA readiness

The current Streamlit interface is responsive and remains the supported web client. A fully installable offline PWA must not be emulated inside Streamlit with injected service-worker JavaScript: Streamlit does not own a stable app-shell route or the authentication boundary needed for safe offline caching.

The next mobile client should consume a thin authenticated API facade while reusing the existing domain services:

- `core.agent_runtime` for agent selection, memory context and provider routing;
- `core.profile_access` as the mandatory namespace authorization boundary;
- `core.vector_rag_v9` for private document retrieval and citations;
- Supabase server access only behind the API facade; the service-role key never enters the browser;
- short-lived authenticated sessions and no prompt, document or memory content in browser caches;
- streaming over Server-Sent Events with an explicit request id and cancellation endpoint;
- a web manifest may cache only static brand assets, never authenticated HTML or API responses.

Recommended cutover sequence:

1. Extract an authenticated `/v1/chat` SSE contract around `execute_agent` without changing Streamlit behavior.
2. Add request cancellation and idempotency, then contract tests for family/profile isolation.
3. Build the installable client against that contract and retain Streamlit as the operational fallback.
4. Run security, accessibility, offline-cache and mobile viewport tests before enabling installation.
