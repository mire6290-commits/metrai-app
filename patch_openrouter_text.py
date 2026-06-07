import os

file_path = 'backend/engines/text_llm_engine.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_method = '''
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_openrouter_text(self, user_msg: str) -> str:
        import requests, os
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        api_key = api_key.strip()
        model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-latest")
        logger.info(f"Sending text to OpenRouter API (model: {model})...")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": [{"role": "user", "content": [{"type": "text", "text": SYSTEM_PROMPT + "\\n\\n" + user_msg}]}]}
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=300)
        if not resp.ok:
            error_msg = f"OpenRouter API failed: {resp.status_code} - {resp.text}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        data = resp.json()
        if "choices" not in data or not data["choices"]:
            raise ValueError(f"OpenRouter returned empty choices: {data}")
        raw_json = data["choices"][0]["message"]["content"]
        raw_json = raw_json.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return raw_json
'''

if 'def _call_openrouter_text' not in content:
    content += new_method

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
