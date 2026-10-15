"""Integer-only cache reallocation; upstream usage is never mutated."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
import secrets
from typing import Callable


@dataclass(frozen=True)
class TokenBuckets:
    input: int
    output: int
    read: int = 0
    creation: int = 0

    def __post_init__(self):
        if any(type(v) is not int or v < 0 for v in asdict(self).values()):
            raise ValueError("usage must contain nonnegative integer token counts")

    @property
    def total(self) -> int:
        return self.input + self.output + self.read + self.creation

    @property
    def context(self) -> int:
        return self.input + self.read + self.creation

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class Allocation:
    raw: TokenBuckets
    effective: TokenBuckets
    baseline: TokenBuckets
    billed: TokenBuckets
    coefficient: int | None = None
    reason: str | None = None

    def to_dict(self) -> dict:
        return {"raw": self.raw.to_dict(), "effective": self.effective.to_dict(),
                "baseline": self.baseline.to_dict(), "billed": self.billed.to_dict(),
                "coefficient": self.coefficient, "reason": self.reason}


class CacheSimulationAllocator:
    FLOOR = 800
    CEILING = 950

    @staticmethod
    def baseline(raw: TokenBuckets, multiplier: float | Decimal) -> TokenBuckets:
        # Match the existing accounting truncation before moving any tokens.
        return TokenBuckets(**{key: int(value * multiplier) for key, value in raw.to_dict().items()})

    @staticmethod
    def feasible_range(raw: TokenBuckets, baseline: TokenBuckets) -> int:
        if raw.total <= 0 or baseline.total <= 0:
            return 0
        return min(950, 1000 * (raw.input + raw.read) // raw.total,
                   1000 * (baseline.input + baseline.read) // baseline.total)

    @staticmethod
    def original(raw: TokenBuckets, baseline: TokenBuckets, reason: str | None = None) -> Allocation:
        return Allocation(raw, raw, baseline, baseline, reason=reason)

    @classmethod
    def allocate(cls, raw: TokenBuckets, baseline: TokenBuckets, multiplier: Decimal,
                 *, coefficient: int | None = None,
                 randbelow: Callable[[int], int] = secrets.randbelow) -> Allocation:
        upper = cls.feasible_range(raw, baseline)
        if multiplier <= 0 or upper < cls.FLOOR:
            return cls.original(raw, baseline, "unreachable_floor")
        if raw.read * 1000 >= raw.total * cls.FLOOR:
            return cls.original(raw, baseline, "upstream_good")
        k = coefficient if coefficient is not None else cls.FLOOR + randbelow(upper - cls.FLOOR + 1)
        if type(k) is not int or not cls.FLOOR <= k <= upper:
            raise ValueError("coefficient is outside the feasible interval")
        read = (raw.total * k + 999) // 1000
        effective = TokenBuckets(raw.input + raw.read - read, raw.output, read, raw.creation)
        pair = baseline.input + baseline.read
        billed_read = min(pair, max(baseline.read, int(Decimal(read) * multiplier),
                                   (baseline.total * k + 999) // 1000))
        billed = TokenBuckets(pair - billed_read, baseline.output, billed_read, baseline.creation)
        assert raw.total == effective.total and baseline.total == billed.total
        return Allocation(raw, effective, baseline, billed, coefficient=k)
