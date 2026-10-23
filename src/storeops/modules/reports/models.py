from dataclasses import dataclass


@dataclass
class StoreMetrics:
    store_id: str
    activities_created: int = 0
    activities_completed: int = 0
    activities_deleted: int = 0
    programmes_created: int = 0
    programme_members_added: int = 0
    templates_applied: int = 0


@dataclass(frozen=True)
class RegionMetrics:
    region_id: str
    store_count: int
    activities_created: int
    activities_completed: int
    activities_deleted: int
    programmes_created: int
    programme_members_added: int
