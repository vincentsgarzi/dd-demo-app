"""
CPU Guard — monitors host-wide CPU and throttles expensive demo operations.

Prevents the demo app from bricking SEs' work laptops / ruining demos.
All services import this; the monitor thread starts once per process.

Thresholds (host CPU %):
  SAFE      < 60%  — full speed, normal caps
  THROTTLE  60-80% — reduce compute n, warn in logs
  CRITICAL  > 80%  — skip expensive ops entirely, return simulated results
"""
import time
import threading
import logging

logger = logging.getLogger("ddstore.cpu_guard")

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False
    logger.warning("psutil not available — CPU guard disabled (run: pip install psutil)")

# ── Thresholds ────────────────────────────────────────────────────────────────
SAFE_PCT     = 60   # below this: everything runs normally
THROTTLE_PCT = 75   # above this: cap expensive compute, slow loadgen
CRITICAL_PCT = 85   # above this: skip computation entirely

# Max n for prime sieve at each tier (intentional bug still fires, just bounded)
COMPUTE_CAP_NORMAL   = 75_000   # ~1-3s on modern hardware
COMPUTE_CAP_THROTTLE = 15_000   # ~0.2s — still causes a visible spike
COMPUTE_CAP_CRITICAL = 0        # skip entirely, return simulated result

# ── Shared state (read from any thread) ──────────────────────────────────────
_cpu_pct: float = 0.0
_lock = threading.Lock()
_last_logged_tier = "safe"


def _poll_loop():
    global _cpu_pct, _last_logged_tier
    while True:
        if _PSUTIL_AVAILABLE:
            try:
                pct = psutil.cpu_percent(interval=2)  # blocks 2s, accurate reading
                with _lock:
                    _cpu_pct = pct

                tier = _tier(pct)
                if tier != _last_logged_tier:
                    _last_logged_tier = tier
                    if tier == "critical":
                        logger.warning(
                            f"CPU guard: CRITICAL ({pct:.0f}%) — skipping all expensive operations to protect host",
                            extra={"cpu_guard": {"pct": pct, "tier": tier, "action": "skip_all"}},
                        )
                    elif tier == "throttle":
                        logger.info(
                            f"CPU guard: THROTTLE ({pct:.0f}%) — capping compute operations",
                            extra={"cpu_guard": {"pct": pct, "tier": tier, "action": "cap_compute"}},
                        )
                    else:
                        logger.info(
                            f"CPU guard: SAFE ({pct:.0f}%) — resuming normal operation",
                            extra={"cpu_guard": {"pct": pct, "tier": tier, "action": "normal"}},
                        )
            except Exception:
                pass
        else:
            time.sleep(5)


def _tier(pct: float) -> str:
    if pct >= CRITICAL_PCT:
        return "critical"
    if pct >= THROTTLE_PCT:
        return "throttle"
    return "safe"


# Start the background monitor — daemon so it never blocks shutdown
_monitor = threading.Thread(target=_poll_loop, daemon=True, name="cpu-guard")
_monitor.start()


# ── Public API ────────────────────────────────────────────────────────────────

def current_pct() -> float:
    """Current host CPU utilisation (0–100)."""
    with _lock:
        return _cpu_pct


def current_tier() -> str:
    """'safe' | 'throttle' | 'critical'"""
    return _tier(current_pct())


def is_throttled() -> bool:
    """True when CPU >= THROTTLE_PCT — cap compute but don't skip."""
    return current_pct() >= THROTTLE_PCT


def is_critical() -> bool:
    """True when CPU >= CRITICAL_PCT — skip expensive ops entirely."""
    return current_pct() >= CRITICAL_PCT


def compute_cap(requested_n: int) -> int:
    """
    Return the CPU-aware cap for the prime sieve n parameter.
    Returns 0 if the computation should be skipped entirely.
    """
    pct = current_pct()
    if pct >= CRITICAL_PCT:
        return COMPUTE_CAP_CRITICAL
    if pct >= THROTTLE_PCT:
        return min(requested_n, COMPUTE_CAP_THROTTLE)
    return min(requested_n, COMPUTE_CAP_NORMAL)


def loadgen_sleep(base_seconds: float) -> float:
    """
    Return an adaptive sleep duration for the load generator.
    Backs off proportionally when CPU is elevated.
    """
    pct = current_pct()
    if pct >= CRITICAL_PCT:
        return base_seconds * 4.0   # very slow down
    if pct >= THROTTLE_PCT:
        return base_seconds * 2.5   # moderate slowdown
    if pct >= SAFE_PCT:
        return base_seconds * 1.5   # slight caution
    return base_seconds             # full speed
