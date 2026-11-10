import rxconfig


def test_reflex_sends_no_telemetry() -> None:
    """Reflex reports every run to PostHog unless told not to: the system, the CPU, the
    memory, the versions. A tool that runs on one person's computer keeps that there."""
    assert rxconfig.config.telemetry_enabled is False


def test_the_development_frontend_listens_only_on_this_computer() -> None:
    """Reflex starts Vite with a bare `--host`, every network interface: anyone on the same
    Wi-Fi reached the development server, a Vite with open advisories that read files."""
    from reflex_base.constants.installer import PackageJson

    assert rxconfig.config.backend_host == "127.0.0.1"
    assert PackageJson.Commands.DEV == "react-router dev --host 127.0.0.1"
