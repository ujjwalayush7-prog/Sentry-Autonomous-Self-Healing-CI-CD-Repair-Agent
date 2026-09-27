"""
Smoke Test for DockerSandbox
Tests DockerSandbox execution logic, volume mounting, container lifecycle,
and error handling. Uses unit mocks to verify behavior on systems where
Docker daemon is not locally running, and live Docker if daemon is active.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from sandbox.docker_sandbox import DockerSandbox, normalize_docker_path
from sandbox.models import ExecutionResult


class TestDockerSandboxSmoke(unittest.TestCase):
    def test_normalize_docker_path(self):
        """Test Windows and Unix path normalization for Docker volume bindings."""
        path = "C:\\Users\\test\\repo"
        normalized = normalize_docker_path(path)
        self.assertNotIn("\\", normalized)
        self.assertTrue(normalized.startswith("C:/") or normalized.startswith("c:/"))

    def test_docker_sandbox_mock_lifecycle(self):
        """
        Verify DockerSandbox container lifecycle:
        create -> start -> wait -> logs -> remove -> ExecutionResult
        """
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 1}
        mock_container.logs.side_effect = [
            b"test_vip_customer_discount FAILED\nAssertionError: Expected 84.0, got 21.0", # stdout
            b"", # stderr
        ]

        mock_client = MagicMock()
        mock_client.containers.create.return_value = mock_container

        sandbox = DockerSandbox(client=mock_client)
        repo_path = os.path.join(BASE_DIR, "test_repos", "hero_python")

        result = sandbox.execute(
            repo_url=repo_path,
            commit_sha=None,
            test_cmd="pytest",
            runtime="python",
        )

        # Assert container was created with correct image and mounted workspace
        mock_client.containers.create.assert_called_once()
        call_kwargs = mock_client.containers.create.call_args[1]
        self.assertEqual(call_kwargs["image"], "python:3.11-slim")
        self.assertEqual(call_kwargs["working_dir"], "/workspace")
        self.assertTrue(any("/workspace" == v["bind"] for v in call_kwargs["volumes"].values()))

        # Assert container lifecycle calls
        mock_container.start.assert_called_once()
        mock_container.wait.assert_called_once()
        mock_container.remove.assert_called_once_with(force=True)

        # Assert structured ExecutionResult
        self.assertFalse(result.passed)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.sandbox_type, "docker")
        self.assertIn("AssertionError", result.stack_trace)

        print("\n[OK] DockerSandbox mock container lifecycle test passed cleanly!")

    def test_live_docker_if_available(self):
        """If real Docker daemon is available, run live test."""
        if not DockerSandbox.is_available():
            print("\n[INFO] Docker daemon is not active on host - skipping live Docker test.")
            return

        print("\n[INFO] Real Docker daemon detected! Running live Docker container test...")
        sandbox = DockerSandbox()
        repo_path = os.path.join(BASE_DIR, "test_repos", "hero_python")
        result = sandbox.execute(
            repo_url=repo_path,
            commit_sha=None,
            test_cmd="python -m pytest",
            runtime="python",
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.sandbox_type, "docker")
        print(f"[OK] Live DockerSandbox executed successfully: exit_code={result.exit_code}")


if __name__ == "__main__":
    unittest.main()
