import asyncio
import logging
import json
import time
import datetime
from typing import Callable, Any, Optional, Union, Coroutine

from .models import JarvisError, ErrorCategory, OperatingState

logger = logging.getLogger("JARVIS.Resilience")


async def with_timeout(
    coro: Coroutine,
    timeout_seconds: float = 30.0,
    error_message: str = "Operation timed out."
) -> Any:
    """
    Executes an asynchronous coroutine with strict timeout and clean cancellation.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"[TIMEOUT] {error_message} (Limit: {timeout_seconds}s)")
        raise TimeoutError(f"{error_message} (Limit: {timeout_seconds}s)")
    except asyncio.CancelledError:
        logger.info("[CANCELLED] Coroutine cancelled during execution.")
        raise


async def safe_retry(
    async_func: Callable[[], Coroutine],
    retries: int = 2,
    backoff: float = 0.2,
    is_idempotent: bool = True,
    operation_name: str = "operation"
) -> Any:
    """
    Retries an idempotent asynchronous operation upon transient failure with backoff.
    NEVER retries non-idempotent or destructive operations.
    """
    if not is_idempotent:
        # Non-idempotent: Execute once only!
        return await async_func()

    last_exc = None
    for attempt in range(1, retries + 2):
        try:
            return await async_func()
        except Exception as e:
            last_exc = e
            if attempt <= retries:
                sleep_time = backoff * (2 ** (attempt - 1))
                logger.warning(
                    f"[RETRY] {operation_name} attempt {attempt} failed: {e}. Retrying in {sleep_time:.2f}s..."
                )
                await asyncio.sleep(sleep_time)
            else:
                logger.error(f"[RETRY_EXHAUSTED] {operation_name} failed after {retries + 1} attempts: {e}")
                raise last_exc


def structured_log(
    event: str,
    level: str = "info",
    state: OperatingState = OperatingState.IDLE,
    error: Optional[Union[JarvisError, str]] = None,
    **kwargs
):
    """
    Emits structured JSON execution logs for observability and audit trails.
    """
    log_data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "event": event,
        "state": state.value if isinstance(state, OperatingState) else str(state),
        "level": level.upper(),
        **kwargs
    }
    if error:
        if isinstance(error, JarvisError):
            log_data["error"] = error.to_dict()
        else:
            log_data["error"] = {"message": str(error)}

    log_line = json.dumps(log_data)
    if level.lower() == "error":
        logger.error(log_line)
    elif level.lower() == "warning":
        logger.warning(log_line)
    elif level.lower() == "critical":
        logger.critical(log_line)
    else:
        logger.info(log_line)
