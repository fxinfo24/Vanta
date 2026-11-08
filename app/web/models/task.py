# app/web/models/task.py
"""
Unified Task model (single source of truth).

Previously this file defined a second, divergent `Task` class mapping to the
same `task` table (string-based status vs. the Enum used in
`app.web.models`). That caused duplicate table registration and inconsistent
status handling. It now re-exports the canonical Task from `__init__.py`.
"""
from . import Task, TaskStatus, db

__all__ = ["Task", "TaskStatus", "db"]
