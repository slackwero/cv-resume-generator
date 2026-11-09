import rxconfig


def test_reflex_sends_no_telemetry() -> None:
    """Reflex reports every run to PostHog unless told not to: the system, the CPU, the
    memory, the versions. A tool that runs on one person's computer keeps that there."""
    assert rxconfig.config.telemetry_enabled is False
