"""
LLM Adapter Factory
Initializes the appropriate LLM adapter based on available credentials.
Priority:
  1. IBM Bob 2.0 / Granite Gateway (BOB_API_KEY)
  2. IBM watsonx.ai SDK (WATSONX_API_KEY + WATSONX_PROJECT_ID)
  3. Google Gemini (GEMINI_API_KEY development fallback)
"""

import os
import logging
from typing import Optional

from dotenv import load_dotenv

from .base import BaseLLMAdapter

logger = logging.getLogger(__name__)

# Automatically load project root .env so uvicorn / CLI scripts pick up BOB_API_KEY
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_FILE = os.path.join(_PROJECT_ROOT, ".env")
if os.path.exists(_ENV_FILE):
    load_dotenv(_ENV_FILE, override=False)


def get_llm_adapter(
    force_provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model_id: Optional[str] = None,
) -> BaseLLMAdapter:
    """
    Returns an LLM adapter instance based on credentials and configuration.

    Args:
        force_provider: 'bob', 'watsonx', or 'gemini' to force a specific provider.
        api_key: Override API key (otherwise reads from environment).
        model_id: Override model ID.
    """
    bob_key = api_key if (api_key and api_key.startswith("bob_")) else (
        os.environ.get("BOB_API_KEY")
        or (os.environ.get("WATSONX_API_KEY") if os.environ.get("WATSONX_API_KEY", "").startswith("bob_") else None)
    )

    if force_provider == "bob" or (force_provider is None and bob_key):
        from .bob_adapter import BobAdapter
        key = api_key or bob_key or ""
        if not key:
            raise ValueError("BOB_API_KEY environment variable required for IBM Bob adapter.")
        logger.info("Initializing BobAdapter (IBM Bob 2.0 / Granite Gateway)")
        return BobAdapter(api_key=key, model_id=model_id)

    if force_provider == "watsonx" or (
        force_provider is None and os.environ.get("WATSONX_API_KEY")
    ):
        from .watsonx_adapter import WatsonxAdapter
        key = api_key or os.environ.get("WATSONX_API_KEY", "")
        project_id = os.environ.get("WATSONX_PROJECT_ID", "")
        url = os.environ.get("WATSONX_URL")
        if not key or not project_id:
            raise ValueError(
                "WATSONX_API_KEY and WATSONX_PROJECT_ID environment variables required "
                "for watsonx adapter."
            )
        logger.info("Initializing WatsonxAdapter (IBM Granite)")
        return WatsonxAdapter(
            api_key=key,
            project_id=project_id,
            url=url,
            model_id=model_id,
        )

    if force_provider == "gemini" or (
        force_provider is None and (api_key or os.environ.get("GEMINI_API_KEY"))
    ):
        from .gemini_adapter import GeminiAdapter
        key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise ValueError("GEMINI_API_KEY environment variable required for Gemini adapter.")
        logger.info("Initializing GeminiAdapter (development fallback)")
        return GeminiAdapter(api_key=key, model_id=model_id)

    raise RuntimeError(
        "No LLM credentials found. Set BOB_API_KEY (for IBM Bob Gateway), "
        "WATSONX_API_KEY + WATSONX_PROJECT_ID (for watsonx.ai), "
        "or GEMINI_API_KEY (for development fallback)."
    )
