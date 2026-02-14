"""Context variables for auto-injecting values into tool calls.

This module provides a mechanism to pass patient_id (and potentially other context)
to tools without requiring the LLM to explicitly pass it in every call.

Uses ContextVar as the primary mechanism (async-safe) with a threading.local()
fallback for thread-pool execution paths where ContextVar may not propagate.

Usage:
    # In agent node (before tool execution):
    from api.agent.tools.context import set_patient_context
    set_patient_context(state.get("patient_id"))

    # In tool (to get patient_id if not provided):
    from api.agent.tools.context import get_patient_context
    if not patient_id:
        patient_id = get_patient_context()
"""

import logging
import threading
from contextvars import ContextVar
from typing import Optional


logger = logging.getLogger(__name__)

# Primary: ContextVar — async-safe, propagates across await boundaries
_current_patient_id: ContextVar[Optional[str]] = ContextVar(
    'current_patient_id',
    default=None
)

# Fallback: thread-local — covers thread-pool execution paths
_thread_local = threading.local()


def set_patient_context(patient_id: Optional[str]) -> None:
    """Set the current patient context for tool auto-injection.

    Writes to both ContextVar (primary) and thread-local (fallback)
    so that tools can retrieve patient_id regardless of execution context.

    Args:
        patient_id: The patient UUID to use for subsequent tool calls,
                   or None to clear the context.
    """
    if patient_id is None:
        logger.warning("[CONTEXT] set_patient_context called with None — tools will have no patient_id fallback")

    _current_patient_id.set(patient_id)
    _thread_local.patient_id = patient_id
    logger.debug("[CONTEXT] patient_id set: %s", patient_id[:8] + "..." if patient_id else "None")


def get_patient_context() -> Optional[str]:
    """Get the current patient context.

    Tries ContextVar first, falls back to thread-local if ContextVar returns None.

    Returns:
        The patient UUID if set, None otherwise.
    """
    # Primary: ContextVar
    patient_id = _current_patient_id.get()

    # Fallback: thread-local (covers thread-pool execution)
    if patient_id is None:
        patient_id = getattr(_thread_local, 'patient_id', None)
        if patient_id is not None:
            logger.info("[CONTEXT] ContextVar was None, recovered patient_id from thread-local: %s", patient_id[:8] + "...")

    if patient_id is None:
        logger.warning("[CONTEXT] get_patient_context returning None — both ContextVar and thread-local are empty")

    return patient_id


def clear_patient_context() -> None:
    """Clear the patient context (sets to None in both stores)."""
    _current_patient_id.set(None)
    _thread_local.patient_id = None
