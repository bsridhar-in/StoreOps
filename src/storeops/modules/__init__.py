"""Feature modules. Each module is layered Routes -> Service -> Repository.

Boundary rules (enforced by ``tests/test_architecture.py``):

* Cross-module imports go through the other module's package (``storeops.modules.<name>``),
  never its internals, and must follow the allowed dependency graph (no cycles).
* ``staff`` is read-only for other modules: they may only use ``StaffReader``/``StaffMember``.
* Notifications (``alerts``) and metrics (``reports``) are driven by the event bus only.
"""
