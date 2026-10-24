"""Allow ``python -m pupdf`` to behave exactly like the ``pupdf`` command."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
