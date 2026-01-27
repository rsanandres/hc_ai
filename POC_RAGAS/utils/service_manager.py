"""Service management for agent API - health checks and auto-restart."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG

# Global reference to service subprocess
_service_process: Optional[subprocess.Popen] = None


async def check_service_health(url: str = None, timeout: float = 5.0) -> bool:
    """Check if agent API service is responding to health checks."""
    if url is None:
        health_url = CONFIG.agent_api_url.replace("/agent/query", "/agent/health")
    else:
        health_url = url
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(health_url)
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "ok"
            return False
    except Exception:
        return False


def start_service(port: int = 8000) -> Optional[subprocess.Popen]:
    """Start the unified API service as a subprocess."""
    global _service_process
    
    # Check if service is already running
    if _service_process and _service_process.poll() is None:
        return _service_process
    
    # Check if port is already in use (another instance might be running)
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        if result == 0:
            # Port is in use, assume service is running
            print(f"Port {port} is already in use - service may already be running")
            return None
    except Exception:
        pass
    
    # Start the service
    try:
        # Change to project root directory
        os.chdir(_REPO_ROOT)
        
        # Start uvicorn service
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "api.main:app",
            "--port",
            str(port),
            "--host",
            "127.0.0.1",
        ]
        
        # Start process in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(_REPO_ROOT),
        )
        
        _service_process = process
        print(f"Started agent API service (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"Failed to start agent API service: {e}")
        return None


async def ensure_service_running(max_attempts: int = 3, wait_time: float = 5.0) -> bool:
    """
    Check if agent API service is running (does NOT start it).
    
    Only checks health - user must start service manually.
    """
    if await check_service_health():
        print("Agent API service is healthy")
        return True
    
    print("Agent API service is NOT running")
    return False


async def restart_service() -> bool:
    """
    Check if service can be restarted (does NOT actually restart).
    
    Returns False to indicate service should be started manually.
    """
    print("Service restart not supported - please start service manually")
    return False


def get_service_process() -> Optional[subprocess.Popen]:
    """Get the current service process, if any."""
    global _service_process
    if _service_process and _service_process.poll() is None:
        return _service_process
    return None


def cleanup_service() -> None:
    """Clean up service process on exit."""
    global _service_process
    if _service_process and _service_process.poll() is None:
        try:
            _service_process.terminate()
            _service_process.wait(timeout=5)
            print("Agent API service stopped")
        except subprocess.TimeoutExpired:
            _service_process.kill()
        except Exception:
            pass
        _service_process = None
