"""Drives the Reflex states of the screens in tests, without a browser or a server.

A state is built the way Reflex builds it for a new tab and its event handlers are
called directly. The `screen_data` fixture (conftest.py) points every state at a
temporary data folder, so a test never reads or writes the real `data/`.
"""

import asyncio
import inspect
from urllib.parse import urlsplit

import reflex as rx
from reflex.event import EventHandler
from reflex.istate.data import RouterData


def new_state[S: rx.State](state_class: type[S], address: str = "") -> S:
    """A state as Reflex builds it for a new tab.

    `_reflex_internal_init` is how Reflex itself does it. It is an internal of the pinned
    Reflex, so an upgrade may need these lines changed. With `address`, the state hangs
    from Reflex's root state, which is where the router lives, opened at that address.
    """
    if not address:
        return state_class(_reflex_internal_init=True)
    root = rx.State(_reflex_internal_init=True)
    root.router = RouterData.from_router_data(
        {"pathname": urlsplit(address).path, "asPath": address, "headers": {"origin": "http://127.0.0.1"}}
    )
    return root.get_substate(state_class.get_full_name().split(".")[1:])


def run(handler: EventHandler, state: rx.State, *args: object) -> object:
    """Calls an event handler as Reflex would and returns what it returned.

    A handler that yields is run to the end, the way the screen waits for it.
    """
    result = handler.fn(state, *args)
    if inspect.isasyncgen(result):

        async def drain() -> None:
            async for _ in result:
                pass

        asyncio.run(drain())
        return None
    if inspect.iscoroutine(result):
        return asyncio.run(result)
    return result
