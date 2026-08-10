import json
import os

USAGE_FILE = "token_usage.json"

def track_usage(agent_id: str, prompt_tokens: int, completion_tokens: int):
    data = {}
    if os.path.exists(USAGE_FILE):
        try:
            with open(USAGE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    
    if agent_id not in data:
        data[agent_id] = {"prompts": 0, "completions": 0, "estimated_cost_usd": 0.0}
    
    data[agent_id]["prompts"] += prompt_tokens
    data[agent_id]["completions"] += completion_tokens
    cost = (prompt_tokens * 0.00000014) + (completion_tokens * 0.00000028)
    data[agent_id]["estimated_cost_usd"] += cost

    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)