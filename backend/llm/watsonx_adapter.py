"""
LLM Adapter - IBM watsonx Granite Implementation
Uses ibm-watsonx-ai SDK to call Granite models for navigation and patch generation.
"""

import json
import logging
from typing import Dict, List, Optional

from .base import BaseLLMAdapter, NavigationResult, PatchResult, SuspectFile
from .prompts import (
    NAVIGATION_SYSTEM_PROMPT,
    PATCH_SYSTEM_PROMPT,
    build_navigation_prompt,
    build_patch_prompt,
)

logger = logging.getLogger(__name__)


class WatsonxAdapter(BaseLLMAdapter):
    """
    Adapter for IBM watsonx.ai Granite models.
    Requires: WATSONX_API_KEY, WATSONX_PROJECT_ID, and optionally WATSONX_URL env vars.
    """

    DEFAULT_MODEL_ID = "ibm/granite-3-8b-instruct"
    DEFAULT_URL = "https://us-south.ml.cloud.ibm.com"

    def __init__(
        self,
        api_key: str,
        project_id: str,
        url: Optional[str] = None,
        model_id: Optional[str] = None,
    ):
        from ibm_watsonx_ai import Credentials
        from ibm_watsonx_ai.foundation_models import ModelInference

        self.model_id = model_id or self.DEFAULT_MODEL_ID
        self._url = url or self.DEFAULT_URL

        credentials = Credentials(api_key=api_key, url=self._url)
        self._model = ModelInference(
            model_id=self.model_id,
            credentials=credentials,
            project_id=project_id,
        )
        logger.info(f"WatsonxAdapter initialized: model={self.model_id}, url={self._url}")

    def get_model_id(self) -> str:
        return self.model_id

    def _call_model(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """Makes a single model inference call and returns raw generated text."""
        # Granite instruct models expect a specific prompt format
        full_prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{user_prompt}\n<|assistant|>\n"

        result = self._model.generate(
            prompt=full_prompt,
            params={
                "max_new_tokens": max_tokens,
                "temperature": 0.1,
                "top_p": 0.95,
                "repetition_penalty": 1.05,
            },
        )
        return result["results"][0]["generated_text"]

    def navigate(
        self,
        stack_trace: str,
        file_tree: str,
        file_contents: Dict[str, str],
        runtime: str,
    ) -> NavigationResult:
        user_prompt = build_navigation_prompt(stack_trace, file_tree, file_contents, runtime)
        raw = self._call_model(NAVIGATION_SYSTEM_PROMPT, user_prompt, max_tokens=4096)
        return _parse_navigation_response(raw, self.model_id)

    def generate_patch(
        self,
        suspect_files: List[SuspectFile],
        file_contents: Dict[str, str],
        stack_trace: str,
        hypothesis: str,
        runtime: str,
    ) -> PatchResult:
        user_prompt = build_patch_prompt(suspect_files, file_contents, stack_trace, hypothesis, runtime)
        raw = self._call_model(PATCH_SYSTEM_PROMPT, user_prompt, max_tokens=4096)
        return _parse_patch_response(raw, self.model_id)


def _parse_navigation_response(raw: str, model_id: str) -> NavigationResult:
    """Parse raw LLM output into structured NavigationResult."""
    try:
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:])
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        import re
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
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        import re
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
