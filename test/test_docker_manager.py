#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DockerManager unit tests.
Covers: data models, size parser, list/remove/stop operations (mocked subprocess).
Run: python3 -m pytest test/test_docker_manager.py -v
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docker_manager import (
    DockerImage, DockerContainer, DockerVolume, DockerResult,
    DockerManager, _parse_docker_size, _run_docker, _run_docker_json,
)


# ─────────────────────────────────────────────
# Data Model Tests
# ─────────────────────────────────────────────

class TestDockerImage(unittest.TestCase):
    def test_full_name(self):
        img = DockerImage(id="abc123", repository="nginx", tag="latest",
                          size=1024, size_human="1KB", created="", created_since="2 days")
        self.assertEqual(img.full_name, "nginx:latest")

    def test_full_name_none_repo(self):
        img = DockerImage(id="abc", repository="<none>", tag="<none>",
                          size=0, size_human="0B", created="", created_since="")
        self.assertEqual(img.full_name, "<none>:<none>")


class TestDockerContainer(unittest.TestCase):
    def test_is_running(self):
        ctr = DockerContainer(id="abc", name="web", image="nginx",
                              status="Up 2 hours", state="running",
                              ports="80/tcp", created="", created_since="", size="")
        self.assertTrue(ctr.is_running)

    def test_is_exited(self):
        ctr = DockerContainer(id="abc", name="web", image="nginx",
                              status="Exited (0)", state="exited",
                              ports="", created="", created_since="", size="")
        self.assertFalse(ctr.is_running)

    def test_is_paused(self):
        ctr = DockerContainer(id="abc", name="web", image="nginx",
                              status="Paused", state="paused",
                              ports="", created="", created_since="", size="")
        self.assertFalse(ctr.is_running)


class TestDockerResult(unittest.TestCase):
    def test_success(self):
        r = DockerResult(True, "done", stdout="ok")
        self.assertTrue(r.success)
        self.assertEqual(r.message, "done")

    def test_failure(self):
        r = DockerResult(False, "failed", stderr="err")
        self.assertFalse(r.success)


# ─────────────────────────────────────────────
# Size Parser Tests
# ─────────────────────────────────────────────

class TestParseDockerSize(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(_parse_docker_size("100B"), 100)

    def test_kb(self):
        self.assertEqual(_parse_docker_size("10KB"), 10 * 1024)

    def test_mb(self):
        self.assertEqual(_parse_docker_size("5MB"), 5 * 1024 ** 2)

    def test_gb(self):
        self.assertEqual(_parse_docker_size("2GB"), 2 * 1024 ** 3)

    def test_tb(self):
        self.assertEqual(_parse_docker_size("1TB"), 1024 ** 4)

    def test_fractional(self):
        self.assertEqual(_parse_docker_size("1.5GB"), int(1.5 * 1024 ** 3))

    def test_empty(self):
        self.assertEqual(_parse_docker_size(""), 0)

    def test_invalid(self):
        self.assertEqual(_parse_docker_size("abc"), 0)

    def test_pure_number(self):
        self.assertEqual(_parse_docker_size("12345"), 12345)

    def test_mib(self):
        self.assertEqual(_parse_docker_size("100MiB"), 100 * 1024 ** 2)

    def test_lowercase(self):
        self.assertEqual(_parse_docker_size("10mb"), 10 * 1024 ** 2)


# ─────────────────────────────────────────────
# _run_docker Tests
# ─────────────────────────────────────────────

class TestRunDocker(unittest.TestCase):
    @patch('docker_manager.subprocess.run')
    def test_run_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="hello\n", stderr="")
        rc, out, err = _run_docker(["ps"])
        self.assertEqual(rc, 0)
        self.assertEqual(out, "hello\n")

    @patch('docker_manager.subprocess.run')
    def test_run_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
        rc, out, err = _run_docker(["rmi", "bad"])
        self.assertEqual(rc, 1)
        self.assertEqual(err, "error msg")

    @patch('docker_manager.shutil.which', return_value=None)
    def test_docker_not_found(self, mock_which):
        with self.assertRaises(FileNotFoundError):
            _run_docker(["ps"])

    @patch('docker_manager.subprocess.run')
    def test_timeout(self, mock_run):
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("docker", 30)
        rc, out, err = _run_docker(["ps"], timeout=30)
        self.assertEqual(rc, -1)
        self.assertIn("timed out", err)


class TestRunDockerJson(unittest.TestCase):
    @patch('docker_manager._run_docker')
    def test_parse_json_lines(self, mock_run):
        data = [
            {"ID": "abc", "Repository": "nginx", "Tag": "latest", "Size": "100MB"},
            {"ID": "def", "Repository": "redis", "Tag": "7", "Size": "50MB"},
        ]
        output = "\n".join(json.dumps(d) for d in data)
        mock_run.return_value = (0, output, "")
        items = _run_docker_json(["images", "--format", "{{json .}}"])
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["Repository"], "nginx")

    @patch('docker_manager._run_docker')
    def test_empty_output(self, mock_run):
        mock_run.return_value = (0, "", "")
        items = _run_docker_json(["images", "--format", "{{json .}}"])
        self.assertEqual(items, [])

    @patch('docker_manager._run_docker')
    def test_error_raises(self, mock_run):
        mock_run.return_value = (1, "", "daemon not running")
        with self.assertRaises(RuntimeError):
            _run_docker_json(["ps"])


# ─────────────────────────────────────────────
# DockerManager Tests (mocked subprocess)
# ─────────────────────────────────────────────

class TestDockerManagerImages(unittest.TestCase):
    @patch('docker_manager._run_docker')
    def test_list_images(self, mock_run):
        data = [
            {"ID": "sha256:abc123def", "Repository": "nginx", "Tag": "latest",
             "Size": "187MB", "CreatedAt": "2026-01-01", "CreatedSince": "6 months"},
            {"ID": "sha256:def456ghi", "Repository": "redis", "Tag": "7",
             "Size": "45MB", "CreatedAt": "2026-06-01", "CreatedSince": "1 month"},
        ]
        output = "\n".join(json.dumps(d) for d in data)
        mock_run.return_value = (0, output, "")
        images = DockerManager.list_images()
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0].repository, "nginx")
        self.assertEqual(images[0].tag, "latest")
        self.assertEqual(images[0].id, "sha256:abc12")
        self.assertEqual(images[1].repository, "redis")

    @patch('docker_manager._run_docker')
    def test_list_images_empty(self, mock_run):
        mock_run.return_value = (0, "", "")
        images = DockerManager.list_images()
        self.assertEqual(images, [])

    @patch('docker_manager._run_docker')
    def test_remove_image_success(self, mock_run):
        mock_run.return_value = (0, "Untagged: nginx:latest\n", "")
        result = DockerManager.remove_image("nginx:latest")
        self.assertTrue(result.success)
        self.assertIn("nginx:latest", result.message)

    @patch('docker_manager._run_docker')
    def test_remove_image_failure(self, mock_run):
        mock_run.return_value = (1, "", "Error: image in use")
        result = DockerManager.remove_image("busy:img")
        self.assertFalse(result.success)
        self.assertIn("Failed", result.message)

    @patch('docker_manager._run_docker')
    def test_remove_images_batch(self, mock_run):
        mock_run.return_value = (0, "removed\n", "")
        results = DockerManager.remove_images(["img1", "img2", "img3"])
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))

    @patch('docker_manager._run_docker')
    def test_remove_image_with_force(self, mock_run):
        mock_run.return_value = (0, "Untagged\n", "")
        result = DockerManager.remove_image("img1", force=True)
        self.assertTrue(result.success)
        # Verify -f flag was passed
        args = mock_run.call_args[0][0]
        self.assertIn("-f", args)


class TestDockerManagerContainers(unittest.TestCase):
    @patch('docker_manager._run_docker')
    def test_list_containers(self, mock_run):
        data = [
            {"ID": "sha256:abc123def456", "Names": "web-server",
             "Image": "nginx:latest", "Status": "Up 2 hours",
             "State": "running", "Ports": "80/tcp",
             "CreatedAt": "2026-01-01", "CreatedSince": "6 months", "Size": "0B"},
            {"ID": "sha256:def456ghi789", "Names": "db-server",
             "Image": "postgres:15", "Status": "Exited (0) 3 hours ago",
             "State": "exited", "Ports": "",
             "CreatedAt": "2026-06-01", "CreatedSince": "1 month", "Size": "10MB"},
        ]
        output = "\n".join(json.dumps(d) for d in data)
        mock_run.return_value = (0, output, "")
        containers = DockerManager.list_containers()
        self.assertEqual(len(containers), 2)
        self.assertEqual(containers[0].name, "web-server")
        self.assertTrue(containers[0].is_running)
        self.assertEqual(containers[1].name, "db-server")
        self.assertFalse(containers[1].is_running)

    @patch('docker_manager._run_docker')
    def test_list_containers_empty(self, mock_run):
        mock_run.return_value = (0, "", "")
        containers = DockerManager.list_containers()
        self.assertEqual(containers, [])

    @patch('docker_manager._run_docker')
    def test_stop_container_success(self, mock_run):
        mock_run.return_value = (0, "abc123\n", "")
        result = DockerManager.stop_container("abc123")
        self.assertTrue(result.success)
        self.assertIn("stopped", result.message)

    @patch('docker_manager._run_docker')
    def test_stop_container_failure(self, mock_run):
        mock_run.return_value = (1, "", "no such container")
        result = DockerManager.stop_container("nonexistent")
        self.assertFalse(result.success)

    @patch('docker_manager._run_docker')
    def test_stop_containers_batch(self, mock_run):
        mock_run.return_value = (0, "stopped\n", "")
        results = DockerManager.stop_containers(["c1", "c2"])
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.success for r in results))

    @patch('docker_manager._run_docker')
    def test_remove_container_success(self, mock_run):
        mock_run.return_value = (0, "abc123\n", "")
        result = DockerManager.remove_container("abc123")
        self.assertTrue(result.success)

    @patch('docker_manager._run_docker')
    def test_remove_container_force(self, mock_run):
        mock_run.return_value = (0, "abc123\n", "")
        result = DockerManager.remove_container("abc123", force=True)
        self.assertTrue(result.success)
        args = mock_run.call_args[0][0]
        self.assertIn("-f", args)

    @patch('docker_manager._run_docker')
    def test_remove_container_failure(self, mock_run):
        mock_run.return_value = (1, "", "container is running")
        result = DockerManager.remove_container("running-ctr")
        self.assertFalse(result.success)
        self.assertIn("Failed", result.message)

    @patch('docker_manager._run_docker')
    def test_remove_containers_batch(self, mock_run):
        mock_run.return_value = (0, "removed\n", "")
        results = DockerManager.remove_containers(["c1", "c2", "c3"])
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))


class TestDockerManagerVolumes(unittest.TestCase):
    @patch('docker_manager._run_docker_json')
    def test_list_volumes(self, mock_json):
        # _run_docker_json is called for both volume ls and volume inspect
        def side_effect(args, timeout=30):
            if args[:2] == ["volume", "ls"]:
                return [
                    {"Name": "vol-data", "Driver": "local"},
                    {"Name": "vol-logs", "Driver": "local"},
                ]
            elif args[:2] == ["volume", "inspect"]:
                name = args[-1]
                return [{
                    "Name": name,
                    "Mountpoint": f"/var/lib/docker/volumes/{name}/_data",
                    "CreatedAt": "2026-01-01T00:00:00Z",
                }]
            return []
        mock_json.side_effect = side_effect

        volumes = DockerManager.list_volumes()
        self.assertEqual(len(volumes), 2)
        self.assertEqual(volumes[0].name, "vol-data")
        self.assertEqual(volumes[0].driver, "local")
        self.assertIn("vol-data", volumes[0].mountpoint)

    @patch('docker_manager._run_docker_json')
    def test_list_volumes_empty(self, mock_json):
        mock_json.return_value = []
        volumes = DockerManager.list_volumes()
        self.assertEqual(volumes, [])

    @patch('docker_manager._run_docker')
    def test_remove_volume_success(self, mock_run):
        mock_run.return_value = (0, "vol-data\n", "")
        result = DockerManager.remove_volume("vol-data")
        self.assertTrue(result.success)
        self.assertIn("vol-data", result.message)

    @patch('docker_manager._run_docker')
    def test_remove_volume_failure(self, mock_run):
        mock_run.return_value = (1, "", "volume in use")
        result = DockerManager.remove_volume("busy-vol")
        self.assertFalse(result.success)
        self.assertIn("Failed", result.message)

    @patch('docker_manager._run_docker')
    def test_remove_volumes_batch(self, mock_run):
        mock_run.return_value = (0, "removed\n", "")
        results = DockerManager.remove_volumes(["v1", "v2", "v3"])
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))

    @patch('docker_manager._run_docker')
    def test_remove_volume_with_force(self, mock_run):
        mock_run.return_value = (0, "removed\n", "")
        result = DockerManager.remove_volume("v1", force=True)
        self.assertTrue(result.success)
        args = mock_run.call_args[0][0]
        self.assertIn("-f", args)


# ─────────────────────────────────────────────
# Utility method tests
# ─────────────────────────────────────────────

class TestDockerManagerUtility(unittest.TestCase):
    @patch('docker_manager._run_docker')
    def test_is_docker_available_true(self, mock_run):
        mock_run.return_value = (0, "docker info output", "")
        self.assertTrue(DockerManager.is_docker_available())

    @patch('docker_manager._run_docker')
    def test_is_docker_available_false(self, mock_run):
        mock_run.return_value = (1, "", "cannot connect")
        self.assertFalse(DockerManager.is_docker_available())

    @patch('docker_manager._run_docker')
    def test_is_docker_available_exception(self, mock_run):
        mock_run.side_effect = Exception("boom")
        self.assertFalse(DockerManager.is_docker_available())


if __name__ == '__main__':
    unittest.main()
