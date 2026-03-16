"""Code sandbox: execute Python code in a subprocess."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid

logger = logging.getLogger(__name__)

SANDBOX_DIR = "/tmp/sandbox_output"
MAX_TIMEOUT = 60


async def execute_code(code: str, timeout: int = 30) -> dict:
    """Execute Python code in a sandboxed subprocess.

    The sandbox has pandas, numpy, matplotlib, plotly available.
    Code can write files to the current working directory.
    Files are saved in /tmp/sandbox_output/{session_id}/

    Returns:
        Dict with keys:
            - stdout: captured standard output (truncated to 50 KB)
            - stderr: captured standard error (truncated to 10 KB)
            - files: list of generated files with URLs
            - success: whether the process exited with code 0
            - error: error message if not successful, else None
            - session_id: unique identifier for this execution
    """
    session_id = str(uuid.uuid4())
    output_dir = os.path.join(SANDBOX_DIR, session_id)
    os.makedirs(output_dir, exist_ok=True)

    # Write code to temp file
    code_file = os.path.join(output_dir, "script.py")
    # Prepend imports and matplotlib backend setting
    preamble = "import matplotlib\nmatplotlib.use('Agg')\n"
    with open(code_file, "w") as f:
        f.write(preamble + code)

    timeout = min(timeout, MAX_TIMEOUT)

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", code_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=output_dir,
            env={**os.environ, "MPLBACKEND": "Agg"},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        stdout_str = stdout.decode("utf-8", errors="replace")[:50000]
        stderr_str = stderr.decode("utf-8", errors="replace")[:10000]
        success = proc.returncode == 0

        # Scan for generated files
        files = []
        for fname in os.listdir(output_dir):
            if fname == "script.py":
                continue
            fpath = os.path.join(output_dir, fname)
            if os.path.isfile(fpath):
                files.append({
                    "filename": fname,
                    "path": fpath,
                    "url": f"/api/sandbox/files/{session_id}/{fname}",
                    "size": os.path.getsize(fpath),
                })

        return {
            "stdout": stdout_str,
            "stderr": stderr_str,
            "files": files,
            "success": success,
            "error": stderr_str if not success else None,
            "session_id": session_id,
        }
    except asyncio.TimeoutError:
        return {
            "stdout": "",
            "stderr": "",
            "files": [],
            "success": False,
            "error": f"Code execution timed out after {timeout}s",
            "session_id": session_id,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": "",
            "files": [],
            "success": False,
            "error": str(e),
            "session_id": session_id,
        }
