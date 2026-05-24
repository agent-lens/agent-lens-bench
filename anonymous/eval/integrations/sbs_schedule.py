from enum import StrEnum
from typing import List, Optional


class SbsRunMode(StrEnum):
    MANUAL = "manual"
    NIGHTLY = "nightly"
    WEEKLY = "weekly"

    @classmethod
    def from_flags(cls, *, is_nightly_mode: bool, is_weekly_mode: bool) -> "SbsRunMode":
        if is_weekly_mode:
            return cls.WEEKLY
        if is_nightly_mode:
            return cls.NIGHTLY
        return cls.MANUAL

    @property
    def is_scheduled(self) -> bool:
        return self is not self.MANUAL

    @property
    def anchor_day_lag(self) -> Optional[int]:
        if self is self.WEEKLY:
            return 7
        elif self is self.NIGHTLY:
            return 1
        else:
            return None

    @property
    def _tracking_tag(self) -> Optional[str]:
        if not self.is_scheduled:
            return None
        return str(self)

    @property
    def tracking_tags(self) -> List:
        tag = self._tracking_tag
        return [tag] if tag is not None else []
