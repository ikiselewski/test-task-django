"""
Query-parameter validation for the genotype API.

Kept free of DRF so the project stays within the env.yml dependency set
(Django only). Views call these helpers and map ValidationError → HTTP 400.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from django.http import QueryDict


class QueryValidationError(Exception):
    """Raised when one or more query parameters are invalid."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        message = '; '.join(f'{k}: {v}' for k, v in self.errors.items())
        super().__init__(message or 'Invalid query parameters')


@dataclass(frozen=True, slots=True)
class GenotypeListFilters:
    """Validated, typed filters for GET /api/get_genotypes/."""

    chromosome: str | None = None
    coordinate: int | None = None
    sample: str | None = None
    assembly: str | None = None


# Align with model field max_lengths where applicable.
_MAX_CHROMOSOME = 50
_MAX_SAMPLE = 100
_MAX_ASSEMBLY = 50


def parse_genotype_list_filters(params: QueryDict | Mapping[str, Any]) -> GenotypeListFilters:
    """
    Parse and validate genotype list query parameters.

    All parameters are optional. When present:
    - ``chromosome``, ``sample``, ``assembly`` must be non-empty strings within
      length limits (after strip).
    - ``coordinate`` must be a positive integer (1-based POS).

    Raises
    ------
    QueryValidationError
        With a mapping of parameter name → human-readable error message.
    """
    errors: dict[str, str] = {}

    chromosome = _optional_str(
        params,
        'chromosome',
        max_length=_MAX_CHROMOSOME,
        errors=errors,
    )
    sample = _optional_str(
        params,
        'sample',
        max_length=_MAX_SAMPLE,
        errors=errors,
    )
    assembly = _optional_str(
        params,
        'assembly',
        max_length=_MAX_ASSEMBLY,
        errors=errors,
    )
    coordinate = _optional_positive_int(params, 'coordinate', errors=errors)

    if errors:
        raise QueryValidationError(errors)

    return GenotypeListFilters(
        chromosome=chromosome,
        coordinate=coordinate,
        sample=sample,
        assembly=assembly,
    )


def _get_raw(params: QueryDict | Mapping[str, Any], name: str) -> str | None:
    if isinstance(params, QueryDict):
        if name not in params:
            return None
        return params.get(name)
    if name not in params:
        return None
    value = params[name]
    if value is None:
        return None
    return str(value)


def _optional_str(
    params: QueryDict | Mapping[str, Any],
    name: str,
    *,
    max_length: int,
    errors: dict[str, str],
) -> str | None:
    raw = _get_raw(params, name)
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        errors[name] = 'Must be a non-empty string when provided.'
        return None
    if len(value) > max_length:
        errors[name] = f'Must be at most {max_length} characters.'
        return None
    return value


def _optional_positive_int(
    params: QueryDict | Mapping[str, Any],
    name: str,
    *,
    errors: dict[str, str],
) -> int | None:
    raw = _get_raw(params, name)
    if raw is None:
        return None
    raw = raw.strip()
    if raw == '':
        errors[name] = 'Must be a positive integer when provided.'
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        errors[name] = 'Must be a positive integer.'
        return None
    if value < 1:
        errors[name] = 'Must be a positive integer (>= 1).'
        return None
    return value
