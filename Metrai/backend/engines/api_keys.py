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
            
    # Override all keys with the new working key
    keys = [
        "AIzaSyCOsrep3DoIvRnkCN7j8B3udbzk-97tYbA"
    ]
        
    chosen = random.choice(keys)
    # Just to trace which key is used (we print partial key)
    logger.info(f"Using Gemini Key: ...{chosen[-6:]}")
    return chosen
