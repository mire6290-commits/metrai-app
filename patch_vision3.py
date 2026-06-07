import re
from pathlib import Path

file_path = 'backend/engines/vision_llm_engine.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace the hardcoded SYSTEM_PROMPT with a dynamic load
new_imports = '''import base64
import io
import json
import logging
import os
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

def load_system_prompt() -> str:
    prompt_path = Path(__file__).parent.parent.parent / "03_prompts" / "system_prompt.txt"
    try:
        return prompt_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to load system prompt: {e}")
        return "You are an expert structural engineer."

SYSTEM_PROMPT = load_system_prompt()
'''

content = re.sub(
    r'import base64[\s\S]*?SYSTEM_PROMPT = """SYSTEM_ROLE[\s\S]*?12\. Never output dims_mm as null object — omit the key entirely if\n      element is linear \(not a plate\)\n"""',
    new_imports,
    content
)

# 2. Modify analyze() to accept pass_mode
analyze_def = '''    def analyze(
        self,
        image: Image.Image,
        page_number: int = 1,
        tile_index: int | None = None,
        context: dict[str, Any] | None = None,
        pass_mode: str = "PASS1"
    ) -> VisionResult:
        context = context or {}
        context["pass_mode"] = pass_mode
        user_msg = self._build_user_message(context)'''

content = re.sub(
    r'    def analyze\([\s\S]*?user_msg = self\._build_user_message\(context\)',
    analyze_def,
    content
)

# 3. Modify _build_user_message
build_msg = '''    @staticmethod
    def _build_user_message(context: dict) -> str:
        lines = []
        pass_mode = context.get("pass_mode", "PASS1")
        lines.append(f"YOU ARE IN {pass_mode}.")
        
        if context:
            lines.append("\\nContext:")
            if "project" in context:
                lines.append(f"- Project: {context['project']}")
            if "ref" in context:
                lines.append(f"- Drawing ref: {context['ref']}")
            if "scale_hint" in context:
                lines.append(f"- Expected scale: {context['scale_hint']}")
            
        lines.append("\\nExtract all required steel profiles and return the JSON format specified for this PASS. Nothing else.")
        return "\\n".join(lines)'''

content = re.sub(
    r'    @staticmethod\n    def _build_user_message\(context: dict\) -> str:[\s\S]*?return "\\n"\.join\(lines\)',
    build_msg,
    content
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched vision_llm_engine.py successfully.")
