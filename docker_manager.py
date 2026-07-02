#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DockerManager -- Docker CLI wrapper for image/container/volume management.
Uses subprocess to invoke docker commands. No third-party dependencies.
"""

import subprocess
import json
import shutil
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ─────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────

@dataclass
class DockerImage:
    id: str
    repository: str
    tag: str
    size: int            # bytes
    size_human: str
    created: str
    created_since: str

    @property
    def full_name(self) -> str:
        return f"{self.repository}:{self.tag}"


@dataclass
class DockerContainer:
    id: str
    name: str
    image: str
    status: str
    state: str          # running, exited, paused, etc.
    ports: str
    created: str
    created_since: str
    size: str           # container size (may be empty)

    @property
    def is_running(self) -> bool:
        return self.state.lower() == "running"


@dataclass
class DockerVolume:
    name: str
    driver: str
    mountpoint: str
    created: str
    # scope, labels etc.


@dataclass
class DockerResult:
    """Generic result from a docker operation."""
    success: bool
    message: str
    stdout: str = ""
    stderr: str = ""


# ─────────────────────────────────────────────
# Helper: run docker command
# ─────────────────────────────────────────────

def _run_docker(args: List[str], timeout: int = 30) -> Tuple[int, str, str]:
    """Run a docker command and return (returncode, stdout, stderr)."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        raise FileNotFoundError("docker executable not found. Is Docker installed?")
    cmd = [docker_bin] + args
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def _run_docker_json(args: List[str], timeout: int = 30):
    """Run docker command with --format json and return parsed objects."""
    rc, stdout, stderr = _run_docker(args, timeout=timeout)
    if rc != 0:
        raise RuntimeError(stderr.strip() or f"docker command failed (rc={rc})")
    # docker --format '{{json .}}' outputs one JSON object per line
    items = []
    for line in stdout.strip().splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


# ─────────────────────────────────────────────
# DockerManager
# ─────────────────────────────────────────────

class DockerManager:
    """High-level API for Docker image/container/volume management."""

    # ── Images ──

    @staticmethod
    def list_images() -> List[DockerImage]:
        """List all docker images."""
        fmt = '{{json .}}'
        items = _run_docker_json([
            "images", "--format", fmt, "--no-trunc"
        ])
        result = []
        for it in items:
            # Size comes as string like "123MB", parse to bytes
            size_str = it.get("Size", "0B")
            size_bytes = _parse_docker_size(size_str)
            result.append(DockerImage(
                id=it.get("ID", "")[:12],
                repository=it.get("Repository", "<none>"),
                tag=it.get("Tag", "<none>"),
                size=size_bytes,
                size_human=size_str,
                created=it.get("CreatedAt", ""),
                created_since=it.get("CreatedSince", ""),
            ))
        return result

    @staticmethod
    def remove_image(image_id: str, force: bool = False) -> DockerResult:
        """Remove a docker image by ID or name."""
        args = ["rmi"]
        if force:
            args.append("-f")
        args.append(image_id)
        rc, stdout, stderr = _run_docker(args)
        if rc == 0:
            return DockerResult(True, f"Image removed: {image_id}", stdout)
        return DockerResult(False, f"Failed to remove image: {stderr.strip()}", stderr=stderr)

    @staticmethod
    def remove_images(image_ids: List[str], force: bool = False) -> List[DockerResult]:
        """Remove multiple images."""
        results = []
        for iid in image_ids:
            results.append(DockerManager.remove_image(iid, force=force))
        return results

    # ── Containers ──

    @staticmethod
    def list_containers(all_states: bool = True) -> List[DockerContainer]:
        """List containers. all_states=True includes stopped containers."""
        fmt = '{{json .}}'
        args = ["ps", "--format", fmt, "--no-trunc"]
        if all_states:
            args.append("-a")
        items = _run_docker_json(args)
        result = []
        for it in items:
            result.append(DockerContainer(
                id=it.get("ID", "")[:12],
                name=it.get("Names", ""),
                image=it.get("Image", ""),
                status=it.get("Status", ""),
                state=it.get("State", ""),
                ports=it.get("Ports", ""),
                created=it.get("CreatedAt", ""),
                created_since=it.get("CreatedSince", ""),
                size=it.get("Size", ""),
            ))
        return result

    @staticmethod
    def stop_container(container_id: str, timeout: int = 10) -> DockerResult:
        """Stop a running container."""
        args = ["stop", "-t", str(timeout), container_id]
        rc, stdout, stderr = _run_docker(args, timeout=timeout + 15)
        if rc == 0:
            return DockerResult(True, f"Container stopped: {container_id}", stdout)
        return DockerResult(False, f"Failed to stop container: {stderr.strip()}", stderr=stderr)

    @staticmethod
    def stop_containers(container_ids: List[str], timeout: int = 10) -> List[DockerResult]:
        """Stop multiple containers."""
        results = []
        for cid in container_ids:
            results.append(DockerManager.stop_container(cid, timeout=timeout))
        return results

    @staticmethod
    def remove_container(container_id: str, force: bool = False) -> DockerResult:
        """Remove a container."""
        args = ["rm"]
        if force:
            args.append("-f")
        args.append(container_id)
        rc, stdout, stderr = _run_docker(args)
        if rc == 0:
            return DockerResult(True, f"Container removed: {container_id}", stdout)
        return DockerResult(False, f"Failed to remove container: {stderr.strip()}", stderr=stderr)

    @staticmethod
    def remove_containers(container_ids: List[str], force: bool = False) -> List[DockerResult]:
        """Remove multiple containers."""
        results = []
        for cid in container_ids:
            results.append(DockerManager.remove_container(cid, force=force))
        return results

    # ── Volumes ──

    @staticmethod
    def list_volumes() -> List[DockerVolume]:
        """List all docker volumes."""
        fmt = '{{json .}}'
        items = _run_docker_json(["volume", "ls", "--format", fmt])
        result = []
        for it in items:
            name = it.get("Name", "")
            driver = it.get("Driver", "")
            # Fetch volume inspect for mountpoint and created time
            mountpoint = ""
            created = ""
            try:
                inspect_items = _run_docker_json(["volume", "inspect", "--format", fmt, name])
                if inspect_items:
                    vi = inspect_items[0]
                    mountpoint = vi.get("Mountpoint", "")
                    created = vi.get("CreatedAt", "")
            except Exception:
                pass
            result.append(DockerVolume(
                name=name,
                driver=driver,
                mountpoint=mountpoint,
                created=created,
            ))
        return result

    @staticmethod
    def remove_volume(volume_name: str, force: bool = False) -> DockerResult:
        """Remove a docker volume."""
        args = ["volume", "rm"]
        if force:
            args.append("-f")
        args.append(volume_name)
        rc, stdout, stderr = _run_docker(args)
        if rc == 0:
            return DockerResult(True, f"Volume removed: {volume_name}", stdout)
        return DockerResult(False, f"Failed to remove volume: {stderr.strip()}", stderr=stderr)

    @staticmethod
    def remove_volumes(volume_names: List[str], force: bool = False) -> List[DockerResult]:
        """Remove multiple volumes."""
        results = []
        for vn in volume_names:
            results.append(DockerManager.remove_volume(vn, force=force))
        return results

    # ── Utility ──

    @staticmethod
    def is_docker_available() -> bool:
        """Check if docker CLI is available and daemon is running."""
        try:
            rc, _, _ = _run_docker(["info"], timeout=5)
            return rc == 0
        except Exception:
            return False

    @staticmethod
    def get_disk_usage() -> dict:
        """Get docker disk usage summary."""
        try:
            items = _run_docker_json(["system", "df", "--format", "{{json .}}"])
            usage = {}
            for it in items:
                t = it.get("Type", "Unknown")
                usage[t] = {
                    "total_count": it.get("TotalCount", "0"),
                    "active": it.get("Active", "0"),
                    "reclaimable": it.get("Reclaimable", "0B"),
                    "size": it.get("Size", "0B"),
                }
            return usage
        except Exception:
            return {}


# ─────────────────────────────────────────────
# Size parser (docker format: "123MB", "1.5GB", "450kB", etc.)
# ─────────────────────────────────────────────

def _parse_docker_size(size_str: str) -> int:
    """Parse docker size string to bytes."""
    if not size_str:
        return 0
    size_str = size_str.strip()
    units = {
        "TB": 1024**4, "GB": 1024**3, "MB": 1024**2, "KB": 1024, "B": 1,
        # Docker sometimes uses lowercase
        "tb": 1024**4, "gb": 1024**3, "mb": 1024**2, "kb": 1024, "b": 1,
        # SI units (docker uses these sometimes)
        "TiB": 1024**4, "GiB": 1024**3, "MiB": 1024**2, "KiB": 1024,
    }
    # Sort by suffix length (longest first to avoid partial matches)
    for suffix in sorted(units, key=len, reverse=True):
        if size_str.endswith(suffix):
            num_str = size_str[:-len(suffix)].strip()
            try:
                return int(float(num_str) * units[suffix])
            except ValueError:
                return 0
    try:
        return int(size_str)
    except ValueError:
        return 0
