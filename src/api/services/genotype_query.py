"""Query layer for genotype listing / filtering."""

from __future__ import annotations

from django.db.models import QuerySet

from api.models import Genotype


class GenotypeQueryService:
    """Build filtered genotype querysets for the HTTP API."""

    @staticmethod
    def base_queryset() -> QuerySet[Genotype]:
        return (
            Genotype.objects
            .select_related(
                'sample',
                'sample__species',
                'coordinate',
                'coordinate__chromosome',
                'coordinate__chromosome__assembly',
                'coordinate__chromosome__assembly__species',
                'ref_allele',
            )
            .order_by(
                'coordinate__chromosome__name',
                'coordinate__position',
                'sample__name',
            )
        )

    @classmethod
    def filter(
        cls,
        *,
        chromosome: str | None = None,
        coordinate: int | None = None,
        sample: str | None = None,
        assembly: str | None = None,
    ) -> QuerySet[Genotype]:
        qs = cls.base_queryset()

        if chromosome:
            qs = qs.filter(coordinate__chromosome__name=chromosome)
        if coordinate is not None:
            qs = qs.filter(coordinate__position=coordinate)
        if sample:
            qs = qs.filter(sample__name=sample)
        if assembly:
            qs = qs.filter(coordinate__chromosome__assembly__name=assembly)

        return qs
