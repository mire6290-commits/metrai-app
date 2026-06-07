import os
import random
import logging

logger = logging.getLogger(__name__)

def get_random_gemini_key() -> str:
    """
    Collects all environment variables starting with GEMINI_API_KEY
    and returns one at random for simple load balancing.
    """
    keys = []
    for k, v in os.environ.items():
        if k.startswith("GEMINI_API_KEY") and v.strip():
            keys.append(v.strip())
            
    if not keys:
        raise EnvironmentError("No GEMINI_API_KEY found in environment variables.")
        
    chosen = random.choice(keys)
    logger.info(f"Using Gemini Key: ...{chosen[-6:]}")
    return chosen

def get_openrouter_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise EnvironmentError("No OPENROUTER_API_KEY found in environment variables.")
    logger.info(f"Using OpenRouter Key: ...{key[-6:]}")
    return key
