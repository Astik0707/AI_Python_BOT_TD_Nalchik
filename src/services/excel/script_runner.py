from __future__ import annotations
from typing import List, Dict, Any, Tuple
import json
import subprocess
import os
import time
from decimal import Decimal


def _convert_decimals(obj):
    """Convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, dict):
        return {key: _convert_decimals(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals(item) for item in obj]
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj


def _run_generate_excel_script(table_data: List[Dict[str, Any]]) -> Tuple[str, bytes]:
    """Run the external /home/adminvm/scripts/generate_excel.py to produce an xlsx.

    Returns tuple (path_on_disk, file_bytes).
    """
    script_path = "/home/adminvm/scripts/generate_excel.py"
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Excel script not found: {script_path}")

    # Convert Decimal objects to float for JSON serialization
    converted_data = _convert_decimals(table_data)
    payload = json.dumps({"table_data": converted_data}, ensure_ascii=False).encode("utf-8")

    # Call script with --json-out so it prints JSON including output path
    proc = subprocess.run(
        ["python", script_path, "--json-out"],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if proc.returncode != 0:
        raise RuntimeError(f"generate_excel.py failed: {proc.stderr.decode('utf-8', errors='ignore')}")

    try:
        info = json.loads(proc.stdout.decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"Invalid JSON from generate_excel.py: {e}; out={proc.stdout[:200]!r}")

    if not info.get("ok"):
        raise RuntimeError(f"Excel generation error: {info}")

    out_path = info.get("path") or "/home/adminvm/scripts/report.xlsx"
    if not os.path.exists(out_path):
        raise FileNotFoundError(f"Excel output not found: {out_path}")

    with open(out_path, "rb") as f:
        data = f.read()

    # Copy to a unique temp file to avoid races if needed
    tmp_path = f"/tmp/report_{int(time.time()*1000)}.xlsx"
    try:
        with open(tmp_path, "wb") as tf:
            tf.write(data)
        # Prefer returning the temp path to keep a stable artifact
        return tmp_path, data
    except Exception:
        # Fallback to original path
        return out_path, data


def build_excel_bytes_via_script(table_data: List[Dict[str, Any]]) -> Tuple[str, bytes]:
    """Public API: generate xlsx using the external script and return (path, bytes)."""
    return _run_generate_excel_script(table_data)


