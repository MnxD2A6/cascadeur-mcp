"""Template installed as events/application_started/c01_startup.py.

PROJECT_SOURCE is filled by the local installer, never by MCP input.
Provenance (Cascadeur 2026.2.2 installation): events_rule.get_event_handlers;
events/application_started/application_started_manager.py defines run().
"""

import sys

PROJECT_SOURCE = "__C01_PROJECT_SOURCE__"


def run():
    if PROJECT_SOURCE not in sys.path:
        sys.path.insert(0, PROJECT_SOURCE)
    from events import scene_idle_manager
    scene_idle_manager.execute_when_idle(_start_when_ready)
    print("C01_STARTUP queued for scene_idle")


def _start_when_ready():
    from cascadeur_mcp.bridge.host import start
    print("C01_STARTUP", start())
