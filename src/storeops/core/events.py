"""In-process event bus and the domain events modules use to talk to each other.

Event types live in ``core`` so that publishers and subscribers never import each other:
``activities`` publishes ``ActivityCreated``; ``alerts`` and ``reports`` subscribe to it
without knowing the ``activities`` module exists.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from storeops.core.clock import utcnow

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    store_id: str
    occurred_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, kw_only=True)
class ActivityCreated(DomainEvent):
    activity_id: str
    title: str
    created_by: str
    assignee_id: str | None


@dataclass(frozen=True, kw_only=True)
class ActivityUpdated(DomainEvent):
    activity_id: str
    title: str
    updated_by: str
    changed_fields: tuple[str, ...]
    status: str
    assignee_id: str | None


@dataclass(frozen=True, kw_only=True)
class ActivityDeleted(DomainEvent):
    activity_id: str
    deleted_by: str


@dataclass(frozen=True, kw_only=True)
class ProgrammeCreated(DomainEvent):
    programme_id: str
    name: str
    created_by: str


@dataclass(frozen=True, kw_only=True)
class ProgrammeMemberAdded(DomainEvent):
    programme_id: str
    programme_name: str
    staff_id: str
    added_by: str


class EventBus:
    """Synchronous, in-process publish/subscribe.

    A failing subscriber is logged and isolated: it never breaks the publisher or other
    subscribers.
    """

    def __init__(self) -> None:
        self._handlers: defaultdict[type[DomainEvent], list[Callable[[Any], None]]] = defaultdict(
            list
        )

    def subscribe[E: DomainEvent](self, event_type: type[E], handler: Callable[[E], None]) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        for handler in list(self._handlers[type(event)]):
            try:
                handler(event)
            except Exception:
                logger.exception("Event handler %r failed for %s", handler, type(event).__name__)
