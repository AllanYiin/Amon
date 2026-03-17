#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Backward-compatible alias for the POSIX compatibility entrypoint.

The preferred name is project_launcher_posix.py because this wrapper applies to
both Linux and macOS. Keep this file so existing references do not break.
"""

from __future__ import annotations

from project_launcher_posix import main


if __name__ == "__main__":
    raise SystemExit(main())
