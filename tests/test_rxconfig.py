import copy

import rxconfig


def test_reflex_sends_no_telemetry() -> None:
    """Reflex reports every run to PostHog unless told not to: the system, the CPU, the
    memory, the versions. A tool that runs on one person's computer keeps that there."""
    assert rxconfig.config.telemetry_enabled is False


def test_the_development_frontend_listens_only_on_this_computer() -> None:
    """Reflex starts Vite with a bare `--host`, every network interface: anyone on the same
    Wi-Fi reached the development server, which serves the project's source files."""
    from reflex_base.constants.installer import PackageJson

    assert rxconfig.config.backend_host == "127.0.0.1"
    assert PackageJson.Commands.DEV == "react-router dev --host 127.0.0.1"


def test_the_page_talks_to_the_backend_on_127_0_0_1() -> None:
    """`localhost` may resolve to ::1 first, where another account on this computer can
    listen on the same port and receive the page's websocket, with the profile in it."""
    config = rxconfig.config

    assert config.api_url.startswith("http://127.0.0.1:")
    assert config.deploy_url is not None
    assert config.deploy_url.startswith("http://127.0.0.1:")


def test_a_port_set_on_the_command_line_keeps_127_0_0_1() -> None:
    """`reflex run --backend-port` and the launcher's single port rewrite the URLs."""
    config = copy.copy(rxconfig.config)

    config._replace_defaults(backend_port=8100, frontend_port=3100)  # noqa: SLF001

    assert config.api_url == "http://127.0.0.1:8100"
    assert config.deploy_url == "http://127.0.0.1:3100"
