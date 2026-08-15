"""Compatibility layer for assistant memory features.

This module now delegates to modules.memory so task logging, preferences,
and feature state use one canonical implementation.
"""

from modules import memory as _mem


def log_user_action(action, details=None):
    """Log user action to assistant history."""
    _mem.log_assistant_action(action, meta=details)
    print(f"[Memory] Logged action: {action}")


def set_user_preference(key, value):
    """Set a user preference in the canonical preference store."""
    _mem.set_preference(key, value)
    print(f"[Memory] Set preference: {key} = {value}")


def get_user_preference(key, default=None):
    """Read user preference from the canonical preference store."""
    return _mem.get_preferences().get(key, default)


def update_feature_registry(feature, enabled=True):
    """Enable or disable a feature in the canonical feature registry."""
    if enabled:
        _mem.enable_feature(feature)
    else:
        _mem.disable_feature(feature)
    print(f"[Feature Learning] {'Enabled' if enabled else 'Disabled'} feature: {feature}")


def learn_feature(feature):
    """Learn a new feature by enabling it in the canonical registry."""
    _mem.enable_feature(feature)
    print(f"[Memory] Learned feature: {feature}")


def log_task(task, details=None):
    """Append a task entry to the canonical task log."""
    _mem.log_task(task, meta=details)
    print(f"[Task Log] Logged task: {task}")


def get_frequent_tasks(top_k=10):
    """Return most frequent tasks from canonical task log."""
    return _mem.get_frequent_tasks(top_n=top_k)


def get_frequent_workflows(top_k=10):
    """Backward-compatible alias for older CLI call sites."""
    return get_frequent_tasks(top_k=top_k)


def get_task_log(limit=50):
    """Return canonical task log entries."""
    return _mem.get_task_log(limit=limit)
