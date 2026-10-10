"""Pure Python summary calculations for branding trend data."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from datetime import date
from numbers import Real
from statistics import fmean


ALLOWED_KEYWORDS = ("퍼스널브랜딩", "이미지메이킹", "스피치")
TREND_STABILITY_THRESHOLD = 0.5
ROUND_DIGITS = 5
INSUFFICIENT_DATA = "데이터 부족"
METRIC_NOTE = (
    "네이버 데이터랩 값은 실제 검색량이 아니라 동일한 조회 조건 안에서 "
    "비교하는 상대 검색 관심도 지수입니다."
)


def _rounded(value: float) -> float:
    return round(value, ROUND_DIGITS)


def _validate_threshold(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("stability_threshold는 0 이상의 숫자여야 합니다.")

    threshold = float(value)
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError("stability_threshold는 0 이상의 유한한 숫자여야 합니다.")
    return threshold


def _normalize_records(
    records: Iterable[Mapping[str, object]],
) -> list[tuple[date, str, float]]:
    normalized = []

    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ValueError(f"records[{index}]는 매핑 형식이어야 합니다.")

        raw_date = record.get("date")
        if not isinstance(raw_date, str):
            raise ValueError(f"records[{index}].date는 YYYY-MM-DD 문자열이어야 합니다.")
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError as error:
            raise ValueError(
                f"records[{index}].date는 유효한 YYYY-MM-DD 날짜여야 합니다."
            ) from error

        keyword = record.get("keyword")
        if keyword not in ALLOWED_KEYWORDS:
            raise ValueError(
                f"records[{index}].keyword는 허용된 세 키워드 중 하나여야 합니다."
            )

        raw_value = record.get("value")
        if isinstance(raw_value, bool) or not isinstance(raw_value, Real):
            raise ValueError(f"records[{index}].value는 숫자여야 합니다.")
        numeric_value = float(raw_value)
        if not math.isfinite(numeric_value) or not 0 <= numeric_value <= 100:
            raise ValueError(
                f"records[{index}].value는 0 이상 100 이하의 유한한 숫자여야 합니다."
            )

        normalized.append((parsed_date, str(keyword), numeric_value))

    return normalized


def _empty_keyword_summary() -> dict[str, object]:
    return {
        "count": 0,
        "average": None,
        "minimum": None,
        "maximum": None,
        "latest_date": None,
        "latest_value": None,
        "recent_4week_average": None,
        "previous_4week_average": None,
        "difference": None,
        "trend": INSUFFICIENT_DATA,
    }


def calculate_summary(
    records: Iterable[Mapping[str, object]],
    *,
    stability_threshold: float = TREND_STABILITY_THRESHOLD,
) -> dict[str, object]:
    """Calculate an explainable summary without Firestore or web dependencies.

    A trend is stable when the absolute difference between the recent and
    previous four-observation averages is at most ``stability_threshold``.
    The default threshold is 0.5 points on the 0-100 relative-interest scale.

    Fewer than four observations cannot produce a recent four-week average.
    Four to seven observations can produce a recent average but cannot produce
    a previous average, difference, or trend.
    """

    threshold = _validate_threshold(stability_threshold)
    normalized = _normalize_records(records)
    grouped: dict[str, list[tuple[date, float]]] = {
        keyword: [] for keyword in ALLOWED_KEYWORDS
    }
    for observed_date, keyword, value in normalized:
        grouped[keyword].append((observed_date, value))

    keyword_summaries: dict[str, dict[str, object]] = {}
    ranking_candidates: list[tuple[str, float]] = []

    for keyword in ALLOWED_KEYWORDS:
        observations = sorted(grouped[keyword], key=lambda item: item[0])
        if not observations:
            keyword_summaries[keyword] = _empty_keyword_summary()
            continue

        values = [value for _, value in observations]
        recent_average_raw = fmean(values[-4:]) if len(values) >= 4 else None
        previous_average_raw = fmean(values[-8:-4]) if len(values) >= 8 else None

        difference_raw = None
        trend = INSUFFICIENT_DATA
        if recent_average_raw is not None and previous_average_raw is not None:
            difference_raw = recent_average_raw - previous_average_raw
            if abs(difference_raw) <= threshold:
                trend = "유지"
            elif difference_raw > threshold:
                trend = "상승"
            else:
                trend = "하락"

        if recent_average_raw is not None:
            ranking_candidates.append((keyword, recent_average_raw))

        keyword_summaries[keyword] = {
            "count": len(values),
            "average": _rounded(fmean(values)),
            "minimum": _rounded(min(values)),
            "maximum": _rounded(max(values)),
            "latest_date": observations[-1][0].isoformat(),
            "latest_value": _rounded(observations[-1][1]),
            "recent_4week_average": (
                _rounded(recent_average_raw)
                if recent_average_raw is not None
                else None
            ),
            "previous_4week_average": (
                _rounded(previous_average_raw)
                if previous_average_raw is not None
                else None
            ),
            "difference": (
                _rounded(difference_raw) if difference_raw is not None else None
            ),
            "trend": trend,
        }

    keyword_order = {keyword: index for index, keyword in enumerate(ALLOWED_KEYWORDS)}
    ranking_candidates.sort(key=lambda item: (-item[1], keyword_order[item[0]]))
    ranking = [
        {
            "rank": rank,
            "keyword": keyword,
            "recent_4week_average": _rounded(recent_average),
        }
        for rank, (keyword, recent_average) in enumerate(ranking_candidates, start=1)
    ]

    all_dates = [observed_date for observed_date, _, _ in normalized]
    return {
        "start_date": min(all_dates).isoformat() if all_dates else None,
        "end_date": max(all_dates).isoformat() if all_dates else None,
        "total_count": len(normalized),
        "metric_note": METRIC_NOTE,
        "trend_rule": {
            "stability_threshold": threshold,
            "stable_when": "abs(difference) <= stability_threshold",
        },
        "keywords": keyword_summaries,
        "ranking": ranking,
    }
