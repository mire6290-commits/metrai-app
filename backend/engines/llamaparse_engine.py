import os
import time
import httpx
import logging

logger = logging.getLogger(__name__)

class LlamaParseEngine:
    def __init__(self):
        self.api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if not self.api_key:
            logger.warning("LLAMA_CLOUD_API_KEY not set!")
        self.base_url = "https://api.cloud.llamaindex.ai/api/parsing"

    def parse_to_markdown(self, file_path: str) -> str:
        """
        Parses a PDF file and returns its content as Markdown using LlamaParse REST API.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        logger.info(f"Uploading {file_path} to LlamaParse via REST API...")
        
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f, "application/pdf")}
                response = httpx.post(
                    f"{self.base_url}/upload", 
                    headers=headers, 
                    files=files,
                    timeout=30.0
                )
                
            response.raise_for_status()
            job_id = response.json()["id"]
            logger.info(f"Job created with ID {job_id}. Waiting for completion...")
            
            # Poll for completion
            while True:
                time.sleep(3)
                status_res = httpx.get(
                    f"{self.base_url}/job/{job_id}",
                    headers=headers,
                    timeout=10.0
                )
                status_res.raise_for_status()
                status = status_res.json()["status"]
                
                if status == "SUCCESS":
                    break
                elif status in ["ERROR", "FAILED"]:
                    raise RuntimeError("LlamaParse job failed.")
                logger.info(f"Job status: {status}...")
                
            # Get result
            res = httpx.get(
                f"{self.base_url}/job/{job_id}/result/markdown",
                headers=headers,
                timeout=30.0
            )
            res.raise_for_status()
            markdown = res.json()["markdown"]
            
            logger.info("Successfully retrieved markdown from LlamaParse.")
            return markdown
            
        except Exception as e:
            logger.error(f"LlamaParse REST API failed: {e}")
            raise RuntimeError(f"LlamaParse extraction failed: {e}")
