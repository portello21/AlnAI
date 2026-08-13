# ROG AI provider policy

The ROG AI provider layer is optional-by-default and cost guarded.

| Provider | Local / cloud | Cost class in ROG | Default | Notes |
|---|---|---:|---|---|
| Docker Model Runner / Qwen3 | Local | LOCAL | Enabled when reachable | Preferred for private/local work |
| NVIDIA NIM | Cloud or self-hosted | FREE for the development path configured here | Opt-in | Requires `NVIDIA_API_KEY` and explicit `NVIDIA_MODEL` |
| DeepSeek | Cloud | PAID | Existing-key compatibility only | Existing deployments may explicitly request `deepseek-*`; new auto routing does not silently opt in |
| OpenAI / Codex | Cloud | PAID | Disabled | Architecture only until explicitly enabled |
| Anthropic / Claude | Cloud | PAID | Disabled | Architecture only until explicitly enabled |

## Cost guard

`ROG_ALLOW_PAID=false` is the safe default. Unknown providers fail closed. No test should make a paid API request.

## Configuration

```toml
ROG_PROVIDER_MODE = "auto"
ROG_ALLOW_PAID = false

# Existing optional provider
DEEPSEEK_API_KEY = "..."

# NVIDIA development endpoint / NIM
NVIDIA_API_KEY = "..."
NVIDIA_MODEL = "<explicit model id from NVIDIA API Catalog>"
# NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Future paid providers; having a key is not sufficient while ROG_ALLOW_PAID=false
OPENAI_API_KEY = "..."
ANTHROPIC_API_KEY = "..."
```

Never commit these values.

## Routing

In `auto`, ROG prefers local Qwen, then an explicitly configured NVIDIA development provider. Existing calls that explicitly request a `deepseek-*` model retain backward compatibility when a DeepSeek key is configured. Provider failures feed an in-process circuit breaker so a repeatedly failing endpoint is temporarily skipped.

## NVIDIA

NVIDIA NIM exposes OpenAI-compatible chat endpoints. NVIDIA documents free NIM offerings and free serverless APIs for development, but quotas and terms are external to this repository and can change. For that reason NVIDIA remains opt-in and requires an explicit model ID rather than silently selecting a remote model.

## OpenAI / Codex and Anthropic / Claude

These are intentionally not called by the V9 router yet. They are treated as paid providers and remain disabled by default. Add their adapters only with mocks/tests first and keep `ROG_ALLOW_PAID=false` unless the owner explicitly chooses otherwise.
