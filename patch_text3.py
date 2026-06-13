import re

file_path = 'backend/engines/text_llm_engine.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

analyze_def = '''    def analyze(self, text_content: str, context: dict[str, Any] = None, pass_mode: str = "PASS3") -> VisionResult:
        if not context:
            context = {}

        user_msg = f"YOU ARE IN {pass_mode}.\\n\\n"
        if pass_mode == "PASS3":
            user_msg += "Please execute PASS 3 — MERGE & DEDUPLICATE on the following JSON outputs from previous passes.\\n"
        else:
            user_msg += "Please extract the steel profiles from the following drawing text data.\\n"

        if context.get("project"):
            user_msg += f"Project: {context['project']}\\n"
        if context.get("ref"):
            user_msg += f"Ref: {context['ref']}\\n"
        
        user_msg += f"\\nData:\\n{text_content}"
        user_msg += "\\n\\nCRITICAL: DO NOT STOP EARLY. Return the final unified JSON schema required by the prompt."'''

content = re.sub(
    r'    def analyze\(self, text_content: str, context: dict\[str, Any\] = None\) -> VisionResult:[\s\S]*?CRITICAL: DO NOT STOP EARLY\. You must extract EVERY SINGLE profile listed in the text data\. Do not truncate the JSON list\. If there are 50 items, output 50 items\."',
    analyze_def,
    content
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched text_llm_engine.py successfully.")
