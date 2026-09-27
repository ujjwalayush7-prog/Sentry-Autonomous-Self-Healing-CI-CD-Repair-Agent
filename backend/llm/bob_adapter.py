"""
LLM Adapter - IBM Bob Gateway & Granite Integration
Connects directly to the IBM Bob Gateway API (https://api.us-east.bob.ibm.com):
  1. Discovers instance_id, team_id, and region_domain via GET /admin/v1/profile
  2. Executes inference via POST /inference/v1/chat/completions
Supports IBM Granite (granite-8b-code-instruct), watsonx Orchestrate (wxO-model),
and IBM Bob multi-model routing tiers (fast, premium).
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional
import requests

from .base import BaseLLMAdapter, NavigationResult, PatchResult, SuspectFile
from .prompts import (
    NAVIGATION_SYSTEM_PROMPT,
    PATCH_SYSTEM_PROMPT,
    build_navigation_prompt,
    build_patch_prompt,
)

logger = logging.getLogger(__name__)

BOB_DEFAULT_BASE_URL = "https://api.us-east.bob.ibm.com"
BOB_USER_AGENT = "IBM Bob/2.2.0"

# Model fallback chain on the IBM Bob Gateway:
# Starts with Granite / Bob models and falls back seamlessly if a tier is busy or produces malformed JSON
BOB_MODEL_CHAIN = [
    "fast",
    "granite-8b-code-instruct",
    "wxO-model",
    "premium",
]


class BobAdapter(BaseLLMAdapter):
    """
    Production adapter for the IBM Bob 2.0 / watsonx Granite Gateway API.
    Authenticates with `bob_prod_bob-apikey_...` keys using the `apikey` scheme,
    resolves active instance/team headers from `/admin/v1/profile`, and calls
    `/inference/v1/chat/completions`.
    """

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ):
        self.api_key = api_key.strip()
        self.base_url = (base_url or os.environ.get("BOB_BASE_URL") or BOB_DEFAULT_BASE_URL).rstrip("/")
        self.nav_model = model_id or os.environ.get("BOB_NAV_MODEL_ID") or "granite-8b-code-instruct"
        self.patch_model = model_id or os.environ.get("BOB_PATCH_MODEL_ID") or "wxO-model"
        self.primary_model = self.nav_model
        self._active_model = f"{self.nav_model} + {self.patch_model}"
        self.instance_id = instance_id or os.environ.get("BOB_INSTANCE_ID")
        self.team_id = team_id or os.environ.get("BOB_TEAM_ID")

        self._resolve_profile()
        logger.info(
            f"BobAdapter initialized: base_url={self.base_url}, "
            f"nav_model={self.nav_model}, patch_model={self.patch_model}, "
            f"instance_id={self.instance_id}, team_id={self.team_id}"
        )

    def _base_headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"apikey {self.api_key}",
            "User-Agent": BOB_USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.instance_id:
            headers["x-instance-id"] = self.instance_id
        if self.team_id:
            headers["x-team-id"] = self.team_id
        return headers

    def _resolve_profile(self) -> None:
        """Queries /admin/v1/profile to populate x-instance-id and x-team-id if not already set."""
        if self.instance_id and self.team_id:
            return

        url = f"{self.base_url}/admin/v1/profile"
        resp = requests.get(url, headers=self._base_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        instances = data.get("instances", [])
        if not instances:
            raise RuntimeError("No active IBM Bob instances found on profile.")

        active_inst = next(
            (inst for inst in instances if inst.get("instance_status") == "active"),
            instances[0],
        )
        self.instance_id = active_inst.get("instance_id")
        teams = active_inst.get("teams", [])
        if teams:
            self.team_id = teams[0].get("id")

        region_domain = active_inst.get("region_domain")
        if region_domain:
            host = region_domain if region_domain.startswith("api.") else f"api.{region_domain}"
            self.base_url = f"https://{host}"

    def get_model_id(self) -> str:
        return f"ibm-bob/{self._active_model}"

    def _call_chat_completion(
        self,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/inference/v1/chat/completions"
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        resp = requests.post(url, headers=self._base_headers(), json=payload, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"IBM Bob inference error ({resp.status_code}) on {model_id}: {resp.text[:400]}")
        return resp.json()

    def navigate(
        self,
        stack_trace: str,
        file_tree: str,
        file_contents: Dict[str, str],
        runtime: str,
    ) -> NavigationResult:
        user_prompt = build_navigation_prompt(stack_trace, file_tree, file_contents, runtime)
        models_to_try = [self.nav_model] + [m for m in BOB_MODEL_CHAIN if m != self.nav_model]

        last_err = None
        for model_id in models_to_try:
            for attempt in range(2):
                try:
                    logger.info(f"IBM Bob Navigate call using model '{model_id}' (attempt {attempt + 1})...")
                    resp_json = self._call_chat_completion(model_id, NAVIGATION_SYSTEM_PROMPT, user_prompt)
                    raw_text = resp_json["choices"][0]["message"]["content"]
                    usage = resp_json.get("usage", {})
                    nav_res = _parse_navigation_response(raw_text, f"ibm-bob/{model_id}")
                    if not nav_res.suspects:
                        raise ValueError("Empty suspects list returned")
                    nav_res.prompt_tokens = usage.get("prompt_tokens")
                    nav_res.completion_tokens = usage.get("completion_tokens")
                    self._active_model = model_id
                    return nav_res
                except Exception as e:
                    last_err = e
                    logger.warning(f"BobAdapter navigate with {model_id} failed: {e}")
                    time.sleep(1)

        raise RuntimeError(f"All IBM Bob models failed navigation. Last error: {last_err}")

    def generate_patch(
        self,
        suspect_files: List[SuspectFile],
        file_contents: Dict[str, str],
        stack_trace: str,
        hypothesis: str,
        runtime: str,
    ) -> PatchResult:
        user_prompt = build_patch_prompt(suspect_files, file_contents, stack_trace, hypothesis, runtime)
        models_to_try = [self.patch_model] + [m for m in BOB_MODEL_CHAIN if m != self.patch_model]

        last_err = None
        for model_id in models_to_try:
            for attempt in range(2):
                try:
                    logger.info(f"IBM Bob Patch call using model '{model_id}' (attempt {attempt + 1})...")
                    resp_json = self._call_chat_completion(model_id, PATCH_SYSTEM_PROMPT, user_prompt)
                    raw_text = resp_json["choices"][0]["message"]["content"]
                    usage = resp_json.get("usage", {})
                    patch_res = _parse_patch_response(raw_text, f"ibm-bob/{model_id}")
                    if not patch_res.unified_diff or "@@" not in patch_res.unified_diff:
                        raise ValueError("Patch response missing valid unified diff @@ hunk header")
                    patch_res.prompt_tokens = usage.get("prompt_tokens")
                    patch_res.completion_tokens = usage.get("completion_tokens")
                    self._active_model = model_id
                    return patch_res
                except Exception as e:
                    last_err = e
                    logger.warning(f"BobAdapter generate_patch with {model_id} failed: {e}")
                    time.sleep(1)

        raise RuntimeError(f"All IBM Bob models failed patch generation. Last error: {last_err}")


def _extract_json_dict(raw: str) -> Dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Could not parse JSON from IBM Bob response: {raw[:500]}")


def _parse_navigation_response(raw: str, model_id: str) -> NavigationResult:
    data = _extract_json_dict(raw)
    suspects = []
    for s in data.get("suspects", []):
        suspects.append(
            SuspectFile(
                rank=int(s.get("rank", len(suspects) + 1)),
                file_path=str(s.get("file_path", "")),
                confidence=float(s.get("confidence", 0.0)),
                reasoning=str(s.get("reasoning", "")),
                suspected_defect=str(s.get("suspected_defect", "")),
                relevant_lines=s.get("relevant_lines"),
            )
        )
    return NavigationResult(
        suspects=suspects,
        reasoning_trace=str(data.get("reasoning_trace", "")),
        files_analyzed=len(suspects),
        model_id=model_id,
    )


def _parse_patch_response(raw: str, model_id: str) -> PatchResult:
    data = _extract_json_dict(raw)
    return PatchResult(
        unified_diff=str(data.get("unified_diff", "")),
        explanation=str(data.get("explanation", "")),
        target_file=str(data.get("target_file", "")),
        model_id=model_id,
        confidence=float(data.get("confidence", 0.0)),
    )
