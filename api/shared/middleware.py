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
        
        log_msg = f"Request: {method} {url}"
        if query:
            log_msg += f"?{query}"
            
        logger.info(log_msg)
        
        # Log body for non-GET requests (if likely JSON)
        if method in ["POST", "PUT", "PATCH"] and not is_health:
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
    """Configure CORS middleware for the FastAPI app."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Next.js default ports
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def setup_logging(app: FastAPI) -> None:
    """Configure logging middleware."""
    app.add_middleware(LoggingMiddleware)
