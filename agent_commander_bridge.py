#!/usr/bin/env python3
"""
Agent Commander Bridge — Python wrapper for agent-commander CLI.

Provides a Pythonic interface to start, monitor, and control AI agents
through the agent-commander npm package. Supports multiple isolation modes:
- direct: run in current process
- screen: run in a detached screen session
- docker: run in an isolated Docker container

Usage:
    from agent_commander_bridge import AgentCommanderBridge, AgentConfig

    bridge = AgentCommanderBridge()
    result = bridge.start_agent(AgentConfig(
        tool="claude",
        working_dir="/path/to/repo",
        prompt="Fix the security vulnerability in issue #58",
        timeout=3600,
    ))
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class IsolationMode(Enum):
    """Agent isolation modes."""
    DIRECT = "direct"
    SCREEN = "screen"
    DOCKER = "docker"


class AgentTool(Enum):
    """Supported AI agent CLI tools."""
    CLAUDE = "claude"
    CODEX = "codex"
    OPENCODE = "opencode"
    QWEN = "qwen"
    GEMINI = "gemini"
    AGENT = "agent"


@dataclass
class AgentConfig:
    """Configuration for a single agent run."""
    tool: str = "claude"
    working_dir: str = "."
    prompt: str = ""
    model: str = ""
    permission_mode: str = "plan"  # plan | readonly | auto
    timeout: int = 3600  # seconds
    max_output_tokens: int = 0  # 0 = unlimited
    environment: dict = field(default_factory=dict)
    extra_args: list[str] = field(default_factory=list)
    append_system_prompt: str = ""
    fallback_model: str = ""
    verbose: bool = False

    # Safety
    dangerously_skip_permissions: bool = False  # Only for direct mode

    # Callbacks
    on_output: Optional[Callable[[str], None]] = None
    on_error: Optional[Callable[[str], None]] = None


@dataclass
class AgentResult:
    """Result of an agent run."""
    success: bool
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    working_dir: str
    error: str = ""

    @property
    def output(self) -> str:
        return self.stdout


@dataclass
class DockerConfig:
    """Docker container configuration for agent isolation."""
    image: str = "ubuntu:22.04"
    memory_limit: str = "4g"
    cpu_limit: str = "2"
    network: str = "host"
    volumes: dict = field(default_factory=dict)  # host_path -> container_path
    env_vars: dict = field(default_factory=dict)
    privileged: bool = False


class AgentCommanderBridge:
    """Python wrapper around the agent-commander CLI."""

    def __init__(
        self,
        agent_commander_path: Optional[str] = None,
        default_timeout: int = 3600,
    ):
        self.agent_commander_path = agent_commander_path or self._find_agent_commander()
        self.default_timeout = default_timeout

    @staticmethod
    def _find_agent_commander() -> str:
        """Find the agent-commander executable."""
        # Check common locations
        for name in ["start-agent", "agent-commander"]:
            try:
                result = subprocess.run(
                    ["which", name],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # Check npm global bin
        try:
            result = subprocess.run(
                ["npm", "bin", "-g"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                npm_bin = result.stdout.strip()
                for name in ["start-agent", "agent-commander"]:
                    path = os.path.join(npm_bin, name)
                    if os.path.isfile(path):
                        return path
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Fallback: assume it's in PATH
        return "start-agent"

    def _build_command(self, config: AgentConfig) -> list[str]:
        """Build the agent-commander command from config."""
        cmd = [self.agent_commander_path]

        # Required: tool
        cmd.extend(["--tool", config.tool])

        # Required: working directory
        cmd.extend(["--working-directory", str(Path(config.working_dir).resolve())])

        # Required: prompt (can be from file)
        if config.prompt:
            cmd.extend(["--prompt", config.prompt])

        # Optional: model
        if config.model:
            cmd.extend(["--model", config.model])

        # Optional: permission mode
        permission_map = {
            "plan": "--permission-mode plan",
            "readonly": "--permission-mode plan",  # safest mapping
            "auto": "--permission-mode auto",
        }
        if config.permission_mode in permission_map:
            cmd.extend(permission_map[config.permission_mode].split())

        # Optional: output format (JSON streaming for parseability)
        if config.tool == "claude":
            cmd.extend(["--output-format", "stream-json"])
            cmd.extend(["--input-format", "stream-json"])
            if config.append_system_prompt:
                cmd.extend(["--append-system-prompt", config.append_system_prompt])
            if config.fallback_model:
                cmd.extend(["--fallback-model", config.fallback_model])
            if config.dangerously_skip_permissions:
                cmd.append("--dangerously-skip-permissions")
            if config.verbose:
                cmd.append("--verbose")

        # Extra args
        if config.extra_args:
            cmd.extend(config.extra_args)

        return cmd

    def _build_docker_command(
        self,
        config: AgentConfig,
        docker_config: DockerConfig,
    ) -> list[str]:
        """Build a docker-run command that wraps agent-commander."""
        container_name = f"hive-agent-{int(time.time())}-{os.getpid()}"

        docker_cmd = [
            "docker", "run",
            "--rm",
            "--name", container_name,
            "--memory", docker_config.memory_limit,
            "--cpus", docker_config.cpu_limit,
            "--network", docker_config.network,
        ]

        # Mount working directory
        workdir = str(Path(config.working_dir).resolve())
        docker_cmd.extend(["-v", f"{workdir}:/workspace"])
        docker_cmd.extend(["-w", "/workspace"])

        # Additional volumes
        for host_path, container_path in docker_config.volumes.items():
            docker_cmd.extend(["-v", f"{host_path}:{container_path}"])

        # Environment variables
        for key, value in {**config.environment, **docker_config.env_vars}.items():
            docker_cmd.extend(["-e", f"{key}={value}"])

        if docker_config.privileged:
            docker_cmd.append("--privileged")

        # Image
        docker_cmd.append(docker_config.image)

        # Agent command
        agent_cmd = self._build_command(config)
        docker_cmd.extend(agent_cmd)

        return docker_cmd

    def _build_screen_command(self, config: AgentConfig, session_name: str) -> list[str]:
        """Build a screen command that wraps agent-commander."""
        agent_cmd = self._build_command(config)
        agent_cmd_str = " ".join(shlex.quote(arg) for arg in agent_cmd)

        screen_cmd = [
            "screen",
            "-dmS", session_name,
            "bash", "-c",
            f"cd {shlex.quote(str(Path(config.working_dir).resolve()))} && {agent_cmd_str}"
        ]
        return screen_cmd

    def start_agent(
        self,
        config: AgentConfig,
        isolation: IsolationMode = IsolationMode.DIRECT,
        docker_config: Optional[DockerConfig] = None,
        session_name: Optional[str] = None,
    ) -> AgentResult:
        """Start an agent and wait for completion.

        Args:
            config: Agent configuration
            isolation: Isolation mode (direct/screen/docker)
            docker_config: Docker config (required for docker mode)
            session_name: Screen session name (required for screen mode)

        Returns:
            AgentResult with success status, output, and timing
        """
        start_time = time.time()

        if isolation == IsolationMode.DIRECT:
            return self._run_direct(config, start_time)
        elif isolation == IsolationMode.SCREEN:
            return self._run_screen(config, session_name or f"hive-{int(start_time)}", start_time)
        elif isolation == IsolationMode.DOCKER:
            return self._run_docker(config, docker_config or DockerConfig(), start_time)
        else:
            raise ValueError(f"Unknown isolation mode: {isolation}")

    def _run_direct(self, config: AgentConfig, start_time: float) -> AgentResult:
        """Run agent directly (in-process)."""
        cmd = self._build_command(config)
        logger.info(f"Running agent: {' '.join(shlex.quote(c) for c in cmd)}")

        env = os.environ.copy()
        env.update(config.environment)

        try:
            stdout_lines: list[str] = []
            stderr_lines: list[str] = []

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=str(Path(config.working_dir).resolve()),
            )

            # Read output in real-time if callbacks provided
            if config.on_output:
                import threading

                def read_stdout():
                    for line in process.stdout:
                        line = line.rstrip('\n')
                        stdout_lines.append(line)
                        if config.on_output:
                            config.on_output(line)

                def read_stderr():
                    for line in process.stderr:
                        line = line.rstrip('\n')
                        stderr_lines.append(line)
                        if config.on_error:
                            config.on_error(line)

                t_out = threading.Thread(target=read_stdout, daemon=True)
                t_err = threading.Thread(target=read_stderr, daemon=True)
                t_out.start()
                t_err.start()

                try:
                    process.wait(timeout=config.timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    duration = time.time() - start_time
                    return AgentResult(
                        success=False,
                        return_code=-1,
                        stdout="\n".join(stdout_lines),
                        stderr="\n".join(stderr_lines),
                        duration_seconds=duration,
                        working_dir=str(Path(config.working_dir).resolve()),
                        error=f"Timeout after {config.timeout}s",
                    )

                t_out.join(timeout=5)
                t_err.join(timeout=5)
            else:
                try:
                    stdout, stderr = process.communicate(timeout=config.timeout)
                    stdout_lines = [stdout] if stdout else []
                    stderr_lines = [stderr] if stderr else []
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                    duration = time.time() - start_time
                    return AgentResult(
                        success=False,
                        return_code=-1,
                        stdout=stdout or "",
                        stderr=stderr or "",
                        duration_seconds=duration,
                        working_dir=str(Path(config.working_dir).resolve()),
                        error=f"Timeout after {config.timeout}s",
                    )

            duration = time.time() - start_time
            return AgentResult(
                success=process.returncode == 0,
                return_code=process.returncode,
                stdout="\n".join(stdout_lines),
                stderr="\n".join(stderr_lines),
                duration_seconds=duration,
                working_dir=str(Path(config.working_dir).resolve()),
                error="" if process.returncode == 0 else f"Process exited with code {process.returncode}",
            )

        except FileNotFoundError as e:
            duration = time.time() - start_time
            return AgentResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=duration,
                working_dir=str(Path(config.working_dir).resolve()),
                error=f"Agent executable not found: {e}",
            )
        except Exception as e:
            duration = time.time() - start_time
            return AgentResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=duration,
                working_dir=str(Path(config.working_dir).resolve()),
                error=str(e),
            )

    def _run_screen(self, config: AgentConfig, session_name: str, start_time: float) -> AgentResult:
        """Run agent in a detached screen session."""
        cmd = self._build_screen_command(config, session_name)
        logger.info(f"Starting screen session: {session_name}")

        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(config.working_dir).resolve()),
        )

        if result.returncode != 0:
            duration = time.time() - start_time
            return AgentResult(
                success=False,
                return_code=result.returncode,
                stdout="",
                stderr=result.stderr,
                duration_seconds=duration,
                working_dir=str(Path(config.working_dir).resolve()),
                error=f"Failed to start screen session: {result.stderr}",
            )

        # Wait for session to finish
        logger.info(f"Waiting for screen session {session_name} to complete...")
        elapsed = time.time() - start_time
        remaining = max(1, config.timeout - int(elapsed))

        try:
            subprocess.run(
                ["screen", "-S", session_name, "-X", "wait", "for", "activity", "done"],
                capture_output=True, timeout=remaining,
            )
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

        # Try to capture output from screen log
        stdout = ""
        stderr = ""
        try:
            # Send hardcopy command to capture output
            subprocess.run(
                ["screen", "-S", session_name, "-X", "hardcopy", "-h",
                 f"/tmp/screen-{session_name}.log"],
                capture_output=True, timeout=10,
            )
            log_path = Path(f"/tmp/screen-{session_name}.log")
            if log_path.exists():
                stdout = log_path.read_text(errors="replace")
        except Exception as e:
            stderr = str(e)

        duration = time.time() - start_time
        return AgentResult(
            success=True,  # Screen started successfully
            return_code=0,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            working_dir=str(Path(config.working_dir).resolve()),
        )

    def _run_docker(self, config: AgentConfig, docker_config: DockerConfig, start_time: float) -> AgentResult:
        """Run agent in a Docker container."""
        cmd = self._build_docker_command(config, docker_config)
        logger.info(f"Running agent in Docker: {' '.join(shlex.quote(c) for c in cmd[:10])}...")

        try:
            process = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=config.timeout + 60,
            )
            duration = time.time() - start_time
            return AgentResult(
                success=process.returncode == 0,
                return_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                duration_seconds=duration,
                working_dir=str(Path(config.working_dir).resolve()),
                error="" if process.returncode == 0 else f"Docker exited with code {process.returncode}",
            )
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return AgentResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                duration_seconds=duration,
                working_dir=str(Path(config.working_dir).resolve()),
                error=f"Docker timeout after {config.timeout}s",
            )

    def stop_screen_session(self, session_name: str) -> bool:
        """Stop a screen session by name."""
        try:
            result = subprocess.run(
                ["screen", "-S", session_name, "-X", "quit"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to stop screen session {session_name}: {e}")
            return False

    def stop_docker_container(self, container_name: str) -> bool:
        """Stop a Docker container by name."""
        try:
            result = subprocess.run(
                ["docker", "stop", "--time", "30", container_name],
                capture_output=True, text=True, timeout=60,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to stop Docker container {container_name}: {e}")
            return False

    def list_screen_sessions(self) -> list[str]:
        """List all active screen sessions."""
        try:
            result = subprocess.run(
                ["screen", "-ls"],
                capture_output=True, text=True, timeout=10,
            )
            sessions = []
            for line in result.stdout.splitlines():
                if "\t" in line:
                    name = line.split("\t")[0].strip().split(".")[-1]
                    sessions.append(name)
            return sessions
        except Exception:
            return []

    def list_docker_containers(self, prefix: str = "hive-agent") -> list[str]:
        """List all active Docker containers with given prefix."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={prefix}", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=10,
            )
            return [name for name in result.stdout.strip().splitlines() if name]
        except Exception:
            return []


# ── Convenience functions ───────────────────────────────────────────────

def run_claude_code(
    working_dir: str,
    prompt: str,
    model: str = "",
    permission_mode: str = "plan",
    timeout: int = 3600,
    extra_args: Optional[list[str]] = None,
) -> AgentResult:
    """Convenience function to run Claude Code directly."""
    bridge = AgentCommanderBridge()
    config = AgentConfig(
        tool="claude",
        working_dir=working_dir,
        prompt=prompt,
        model=model,
        permission_mode=permission_mode,
        timeout=timeout,
        extra_args=extra_args or [],
    )
    return bridge.start_agent(config, isolation=IsolationMode.DIRECT)


if __name__ == "__main__":
    """CLI test entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Agent Commander Bridge CLI")
    parser.add_argument("--tool", default="claude", help="Agent tool to use")
    parser.add_argument("--working-dir", default=".", help="Working directory")
    parser.add_argument("--prompt", required=True, help="Prompt for the agent")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    parser.add_argument("--mode", default="direct", choices=["direct", "screen", "docker"])
    parser.add_argument("--json", action="store_true", help="Output result as JSON")

    args = parser.parse_args()

    bridge = AgentCommanderBridge()
    config = AgentConfig(
        tool=args.tool,
        working_dir=args.working_dir,
        prompt=args.prompt,
        timeout=args.timeout,
    )
    mode = IsolationMode(args.mode)

    result = bridge.start_agent(config, isolation=mode)

    if args.json:
        print(json.dumps({
            "success": result.success,
            "return_code": result.returncode,
            "duration_seconds": round(result.duration_seconds, 1),
            "output": result.stdout,
            "error": result.stderr or result.error,
        }, indent=2))
    else:
        if result.success:
            print(f"\u2705 Agent completed in {result.duration_seconds:.1f}s")
            if result.stdout:
                print(result.stdout)
        else:
            print(f"\u274c Agent failed (code {result.returncode}) in {result.duration_seconds:.1f}s")
            if result.error:
                print(f"Error: {result.error}")
            if result.stderr:
                print(result.stderr)
            sys.exit(1)
