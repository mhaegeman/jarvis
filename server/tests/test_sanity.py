"""Toolchain sanity check."""

import server


def test_package_importable() -> None:
    assert server.__version__ == "0.0.1"


def test_pytest_asyncio_works() -> None:
    """Ensures pytest-asyncio in auto mode is loaded."""
    import asyncio

    assert asyncio.get_event_loop_policy() is not None
