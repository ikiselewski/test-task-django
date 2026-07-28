"""
HTTP API views.

Implemented as Django class-based views (see Django docs:
https://docs.djangoproject.com/en/5.1/topics/class-based-views/).

Endpoint
--------
GET /api/get_genotypes/
    Query params (all optional):
      chromosome  — exact CHROM match (e.g. chr1)
      coordinate  — exact 1-based POS (integer; non-integers ignored)
      sample      — sample name (e.g. HG001)
      assembly    — assembly name (e.g. GRCh38)
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views import View

from .serializers import serialize_genotype_list
from .services import GenotypeQueryService


class GenotypeListView(View):
    """
    Class-based list endpoint for genotype records.

    Only GET is supported. Filtering is applied in GenotypeQueryService so the
    view stays thin (HTTP concerns only).
    """

    http_method_names = ['get', 'head', 'options']

    def get(self, request: HttpRequest, *args, **kwargs) -> JsonResponse:
        chromosome = self._query_str(request, 'chromosome')
        coordinate = self._query_int(request, 'coordinate')
        sample = self._query_str(request, 'sample')
        assembly = self._query_str(request, 'assembly')

        queryset = GenotypeQueryService.filter(
            chromosome=chromosome,
            coordinate=coordinate,
            sample=sample,
            assembly=assembly,
        )

        payload = serialize_genotype_list(queryset)
        return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})

    # ------------------------------------------------------------------
    # query parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _query_str(request: HttpRequest, name: str) -> str | None:
        value = request.GET.get(name)
        if value is None:
            return None
        value = value.strip()
        return value or None

    @staticmethod
    def _query_int(request: HttpRequest, name: str) -> int | None:
        """
        Parse an integer query param.

        Non-integer values are ignored (do not raise), matching the OpenAPI
        contract for ``coordinate``.
        """
        raw = request.GET.get(name)
        if raw is None or raw == '':
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
