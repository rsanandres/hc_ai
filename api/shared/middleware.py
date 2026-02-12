import os
import time
import json
import logging
from typing import Callable
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Configure logger
logger = logging.getLogger("api.access")
logger.setLevel(logging.INFO)
# Avoid duplicating logs if root logger is already configured
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Log request details
        method = request.method
        url = request.url.path
        query = request.url.query
        
        # Don't log health check bodies to avoid noise, but log the access
        is_health = "health" in url or "stats" in url
        is_streaming = "/stream" in url  # Skip body logging for streaming endpoints
        
        log_msg = f"Request: {method} {url}"
        if query:
            log_msg += f"?{query}"
            
        logger.info(log_msg)
        
        # Log body for non-GET requests (if likely JSON)
        # IMPORTANT: Skip body logging for streaming endpoints because it breaks SSE
        if method in ["POST", "PUT", "PATCH"] and not is_health and not is_streaming:
            try:
                body_bytes = await request.body()
                # Restore body for downstream
                async def receive():
                    return {"type": "http.request", "body": body_bytes, "more_body": False}
                request._receive = receive
                
                if body_bytes:
                    try:
                        body_json = json.loads(body_bytes)
                        logger.info(f"Body: {json.dumps(body_json, indent=2)}")
                    except json.JSONDecodeError:
                        logger.info(f"Body (raw): {body_bytes.decode('utf-8')[:1000]}")
            except Exception as e:
                logger.error(f"Failed to log body: {e}")
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        status_code = response.status_code
        
        logger.info(f"Response: {status_code} in {process_time:.4f}s")
        return response

def setup_cors(app: FastAPI) -> None:
    """Configure CORS middleware for the FastAPI app.

    Set CORS_ORIGINS env var (comma-separated) for production.
    Falls back to localhost for development.
    """
    cors_env = os.environ.get("CORS_ORIGINS", "")
    if cors_env:
        origins = [o.strip() for o in cors_env.split(",") if o.strip()]
    else:
        origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def setup_logging(app: FastAPI) -> None:
    """Configure logging middleware."""
    app.add_middleware(LoggingMiddleware)
