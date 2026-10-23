"""Fixed in-code catalog of planogram task templates.

Each template is a named set of task definitions that
``ActivityService.clone_template_into_programme`` turns into real ``Activity`` records. There
is exactly one template today, ``"standard_planogram_reset"``; adding another named template
is an additive change to ``PLANOGRAM_TEMPLATES``.
"""

from __future__ import annotations

from dataclasses import dataclass

from storeops.modules.activities.models import ActivityPriority


@dataclass(frozen=True)
class PlanogramTaskDefinition:
    """A single task in a planogram template, before it becomes an ``Activity``."""

    title: str
    description: str
    department: str
    priority: ActivityPriority


PLANOGRAM_TEMPLATES: dict[str, tuple[PlanogramTaskDefinition, ...]] = {
    "standard_planogram_reset": (
        PlanogramTaskDefinition(
            title="Update endcap signage",
            description="Replace endcap signage with the current promotional set.",
            department="Merchandising",
            priority=ActivityPriority.MEDIUM,
        ),
        PlanogramTaskDefinition(
            title="Reset shelf layout - Aisle 1-4",
            description="Rearrange shelf facings in aisles 1-4 to match the new planogram.",
            department="Merchandising",
            priority=ActivityPriority.HIGH,
        ),
        PlanogramTaskDefinition(
            title="Verify planogram compliance photos uploaded",
            description="Confirm before/after photos for the reset are uploaded for audit.",
            department="Compliance",
            priority=ActivityPriority.HIGH,
        ),
        PlanogramTaskDefinition(
            title="Restock promotional display",
            description="Restock the promotional display to full capacity.",
            department="Inventory",
            priority=ActivityPriority.URGENT,
        ),
    )
}
