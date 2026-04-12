import asyncio
import glob
import os
import shutil
from pathlib import Path


class Commands:
    def __init__(self, sandbox_dir: str) -> None:
        self.sandbox_dir = sandbox_dir

    async def run(self, command: str, timeout: int = 300) -> dict:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=self.sandbox_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
                return {
                    "exit_code": proc.returncode,
                    "stdout": stdout_bytes.decode(errors="replace"),
                    "stderr": stderr_bytes.decode(errors="replace"),
                }
            except (asyncio.TimeoutError, asyncio.CancelledError):
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.communicate(), timeout=5)
                except Exception:
                    pass
                return {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout} seconds: {command}",
                }

        except Exception as exc:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Failed to execute command '{command}': {exc}",
            }


class Files:
    def __init__(self, sandbox_dir: str) -> None:
        self.sandbox_dir = sandbox_dir

    def _full_path(self, path: str) -> Path:
        full = (Path(self.sandbox_dir) / path).resolve()
        sandbox_root = Path(self.sandbox_dir).resolve()
        if not str(full).startswith(str(sandbox_root)):
            raise ValueError(f"Path traversal denied: {path}")
        return full

    async def write(self, path: str, content: str) -> None:
        full = self._full_path(path)
        await asyncio.to_thread(full.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(full.write_text, content, encoding="utf-8")

    async def read(self, path: str) -> str:
        full = self._full_path(path)
        if not full.exists():
            raise FileNotFoundError(f"File not found in sandbox: {path}")
        return await asyncio.to_thread(full.read_text, encoding="utf-8")

    def list_files(self, pattern: str) -> list[str]:
        full_pattern = str(Path(self.sandbox_dir) / pattern)
        matches = glob.glob(full_pattern, recursive=True)
        return [
            os.path.relpath(match, self.sandbox_dir).replace("\\", "/")
            for match in matches
        ]

    def exists(self, path: str) -> bool:
        return self._full_path(path).exists()


class DamlSandbox:
    BASE_DIR = "/tmp/daml_sandboxes"

    def __init__(self, project_id: str, project_name: str) -> None:
        self.project_id = project_id
        self.project_name = project_name
        self.sandbox_dir = str(Path(self.BASE_DIR) / project_id)

        self.commands = Commands(self.sandbox_dir)
        self.files = Files(self.sandbox_dir)

        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        sandbox_path = Path(self.sandbox_dir)
        daml_dir = sandbox_path / "daml"
        dist_dir = sandbox_path / ".daml" / "dist"

        await asyncio.to_thread(sandbox_path.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(daml_dir.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(dist_dir.mkdir, parents=True, exist_ok=True)

        daml_yaml = (
            "sdk-version: 2.10.3\n"
            f"name: {self.project_name}\n"
            "version: 0.0.1\n"
            "source: daml\n"
            "dependencies:\n"
            "  - daml-prim\n"
            "  - daml-stdlib\n"
        )
        await self.files.write("daml.yaml", daml_yaml)

        main_daml = "module Main where\n"
        await self.files.write("daml/Main.daml", main_daml)

        self._initialized = True

    def get_absolute_path(self, relative_path: str) -> str:
        return str(Path(self.sandbox_dir) / relative_path)

    async def cleanup(self) -> None:
        sandbox_path = Path(self.sandbox_dir)
        if sandbox_path.exists():
            await asyncio.to_thread(shutil.rmtree, self.sandbox_dir, ignore_errors=True)
        self._initialized = False

    def __repr__(self) -> str:
        return (
            f"DamlSandbox("
            f"project_id={self.project_id!r}, "
            f"project_name={self.project_name!r}, "
            f"initialized={self._initialized})"
        )
