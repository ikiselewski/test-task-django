"""
HTTP API views.

Implemented as Django class-based views (see Django docs:
https://docs.djangoproject.com/en/5.1/topics/class-based-views/).

Endpoint
--------
GET /api/get_genotypes/
    Query params (all optional):
      chromosome  — exact CHROM match (e.g. chr1)
      coordinate  — exact 1-based POS (positive integer)
      sample      — sample name (e.g. HG001)
      assembly    — assembly name (e.g. GRCh38)

    Invalid query params → 400 JSON error.
    Missing / outdated DB schema → 503 JSON error.
"""

from __future__ import annotations

import logging

from django.db import DatabaseError, OperationalError
from django.http import HttpRequest, JsonResponse
from django.views import View

from .query_params import QueryValidationError, parse_genotype_list_filters
from .serializers import serialize_genotype_list
from .services import GenotypeQueryService

logger = logging.getLogger(__name__)

_DB_NOT_READY_HINT = (
    'Database schema is missing or outdated. '
    'Run: python manage.py migrate '
    'then load data with: python manage.py load_vcf <file.vcf>'
)


class GenotypeListView(View):
    """
    Class-based list endpoint for genotype records.

    Only GET is supported. Filtering is applied in GenotypeQueryService so the
    view stays thin (HTTP concerns only).
    """

    http_method_names = ['get', 'head', 'options']

    def get(self, request: HttpRequest, *args, **kwargs) -> JsonResponse:
        try:
            filters = parse_genotype_list_filters(request.GET)
        except QueryValidationError as exc:
            return JsonResponse(
                {
                    'error': 'Invalid query parameters',
                    'details': exc.errors,
                },
                status=400,
            )

        try:
            queryset = GenotypeQueryService.filter(
                chromosome=filters.chromosome,
                coordinate=filters.coordinate,
                sample=filters.sample,
                assembly=filters.assembly,
            )
            payload = serialize_genotype_list(queryset)
        except OperationalError as exc:
            logger.exception('Database not ready for genotype query')
            return JsonResponse(
                {
                    'error': 'Database not ready',
                    'detail': _DB_NOT_READY_HINT,
                    'cause': str(exc),
                },
                status=503,
            )
        except DatabaseError as exc:
            logger.exception('Database error during genotype query')
            return JsonResponse(
                {
                    'error': 'Database error',
                    'detail': 'A database error occurred while querying genotypes.',
                    'cause': str(exc),
                },
                status=500,
            )

        return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})
