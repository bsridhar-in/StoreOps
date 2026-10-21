"""Cross-cutting infrastructure shared by all modules.

``core`` must never import from ``storeops.modules``; modules depend on core, not the reverse.
"""
