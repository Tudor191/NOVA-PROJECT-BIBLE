"""`filesystem` built-in adapter (TDD 3C §3): path-prefix allow-list,
checked against the canonicalized/resolved path, before every
read/write/list call. Blocking file I/O runs in a worker thread
(`asyncio.to_thread`) -- this project's standing "no blocking call on the
event loop" discipline, applied here the same way every other engine
applies it to its own repository layer.
"""

from __future__ import annotations

import asyncio

from nova_capability_engine.domain.sandbox import SandboxViolation, resolve_within_roots

__all__ = ["FilesystemAdapter"]


class FilesystemAdapter:
    name = "filesystem"

    async def invoke(
        self, operation: str, parameters: dict, *, required_resources: list[str]
    ) -> dict:
        if operation == "read":
            return await asyncio.to_thread(self._read, parameters, required_resources)
        if operation == "write":
            return await asyncio.to_thread(self._write, parameters, required_resources)
        if operation == "list":
            return await asyncio.to_thread(self._list, parameters, required_resources)
        raise ValueError(f"filesystem adapter does not support operation {operation!r}")

    def _read(self, parameters: dict, allowed_roots: list[str]) -> dict:
        path = resolve_within_roots(parameters["path"], allowed_roots=allowed_roots)
        if not path.is_file():
            raise SandboxViolation(f"{path} is not a readable file", adapter="filesystem")
        return {"content": path.read_text()}

    def _write(self, parameters: dict, allowed_roots: list[str]) -> dict:
        path = resolve_within_roots(parameters["path"], allowed_roots=allowed_roots)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(parameters.get("content", ""))
        return {"bytes_written": path.stat().st_size}

    def _list(self, parameters: dict, allowed_roots: list[str]) -> dict:
        path = resolve_within_roots(
            parameters.get("path", allowed_roots[0]), allowed_roots=allowed_roots
        )
        if not path.is_dir():
            raise SandboxViolation(f"{path} is not a listable directory", adapter="filesystem")
        return {"entries": sorted(p.name for p in path.iterdir())}
