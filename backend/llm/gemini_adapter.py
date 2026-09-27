"""
LLM Adapter - Google Gemini Implementation
Development/fallback adapter using Google GenAI SDK.
Includes automatic retry with exponential backoff and model fallback chain.
"""

import json
import logging
import re
import time
from typing import Dict, List, Optional

from .base import BaseLLMAdapter, NavigationResult, PatchResult, SuspectFile
from .prompts import (
    NAVIGATION_SYSTEM_PROMPT,
    PATCH_SYSTEM_PROMPT,
    build_navigation_prompt,
    build_patch_prompt,
)

logger = logging.getLogger(__name__)

# Model fallback chain: try each in order until one responds
MODEL_FALLBACK_CHAIN = [
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]


class GeminiAdapter(BaseLLMAdapter):
    """
    Adapter for Google Gemini models via the google-genai SDK.
    Supports automatic retry with exponential backoff and model fallback.
    """

    def __init__(self, api_key: str, model_id: Optional[str] = None):
        from google import genai
        self.model_id = model_id or MODEL_FALLBACK_CHAIN[0]
        self._api_key = api_key
        self._client = genai.Client(api_key=api_key)
        self._active_model = self.model_id
        logger.info(f"GeminiAdapter initialized: primary_model={self.model_id}")

    def get_model_id(self) -> str:
        return self._active_model

    def _call_model(self, system_prompt: str, user_prompt: str) -> str:
        """
        Makes a model call with retry and fallback chain.
        On 503/429, retries with backoff then falls back to next model in chain.
        """
        from google.genai import types

        # Build model list: start with requested model, then fallback chain
        models_to_try = [self.model_id]
        for m in MODEL_FALLBACK_CHAIN:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error = None
        for model_id in models_to_try:
            for attempt in range(2):  # 2 attempts per model before switching
                try:
                    logger.info(f"Calling {model_id} (attempt {attempt + 1})...")
                    response = self._client.models.generate_content(
                        model=model_id,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.1,
                            top_p=0.95,
                            response_mime_type="application/json",
                        ),
                    )
                    self._active_model = model_id
                    return response.text
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                        wait_time = 2 * (attempt + 1)
                        logger.warning(
                            f"{model_id} unavailable (attempt {attempt + 1}/2), "
                            f"waiting {wait_time}s..."
                        )
                        time.sleep(wait_time)
                        continue
                    elif "404" in err_str or "NOT_FOUND" in err_str:
                        logger.warning(f"{model_id} not found/deprecated, trying next model...")
                        break  # Skip to next model immediately
                    else:
                        raise  # Unknown error, don't retry

            logger.warning(f"Model {model_id} exhausted retries, trying next fallback...")

        raise RuntimeError(
            f"All models in fallback chain exhausted. Last error: {last_error}"
        )

    def navigate(
        self,
        stack_trace: str,
        file_tree: str,
        file_contents: Dict[str, str],
        runtime: str,
    ) -> NavigationResult:
        user_prompt = build_navigation_prompt(stack_trace, file_tree, file_contents, runtime)
        raw = self._call_model(NAVIGATION_SYSTEM_PROMPT, user_prompt)
        return _parse_navigation_response(raw, self._active_model)

    def generate_patch(
        self,
        suspect_files: List[SuspectFile],
        file_contents: Dict[str, str],
        stack_trace: str,
        hypothesis: str,
        runtime: str,
    ) -> PatchResult:
        user_prompt = build_patch_prompt(suspect_files, file_contents, stack_trace, hypothesis, runtime)
        raw = self._call_model(PATCH_SYSTEM_PROMPT, user_prompt)
        return _parse_patch_response(raw, self._active_model)


def _parse_navigation_response(raw: str, model_id: str) -> NavigationResult:
    """Parse raw LLM output into structured NavigationResult."""
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:])
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Could not parse navigation response as JSON: {raw[:500]}")

    suspects = []
    for s in data.get("suspects", []):
        suspects.append(SuspectFile(
            rank=s.get("rank", 0),
            file_path=s.get("file_path", ""),
            confidence=float(s.get("confidence", 0.0)),
            reasoning=s.get("reasoning", ""),
            suspected_defect=s.get("suspected_defect", ""),
            relevant_lines=s.get("relevant_lines"),
        ))

    return NavigationResult(
        suspects=suspects,
        reasoning_trace=data.get("reasoning_trace", ""),
        files_analyzed=len(suspects),
        model_id=model_id,
    )


def _parse_patch_response(raw: str, model_id: str) -> PatchResult:
    """Parse raw LLM output into structured PatchResult."""
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:])
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Could not parse patch response as JSON: {raw[:500]}")

    return PatchResult(
        unified_diff=data.get("unified_diff", ""),
        explanation=data.get("explanation", ""),
        target_file=data.get("target_file", ""),
        model_id=model_id,
        confidence=float(data.get("confidence", 0.0)),
    )
