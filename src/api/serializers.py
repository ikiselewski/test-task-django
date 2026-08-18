"""
Serializers for genotype API responses.

Uses DRF ``serializers.ModelSerializer`` so the public JSON shape is declared
against the ``Genotype`` model instead of being assembled by hand.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from rest_framework import serializers

from .models import Genotype


class EmptyAsNullCharField(serializers.CharField):
    """Serialize blank strings as JSON null (OpenAPI nullable fields)."""

    def to_representation(self, value: Any) -> str | None:
        represented = super().to_representation(value)
        return represented or None


class GenotypeSerializer(serializers.ModelSerializer):
    """
    Public genotype row.

    Related biology-graph fields are flattened to match the OpenAPI contract
    (chromosome, coordinate, ref, sample, assembly, species).
    """

    chromosome = serializers.CharField(
        source='coordinate.chromosome.name',
        read_only=True,
    )
    coordinate = serializers.IntegerField(
        source='coordinate.position',
        read_only=True,
    )
    ref = serializers.CharField(
        source='ref_allele.sequence',
        read_only=True,
    )
    sample = serializers.CharField(
        source='sample.name',
        read_only=True,
    )
    assembly = serializers.CharField(
        source='coordinate.chromosome.assembly.name',
        read_only=True,
    )
    species = serializers.CharField(
        source='coordinate.chromosome.assembly.species.name',
        read_only=True,
    )
    gt = EmptyAsNullCharField(read_only=True)
    rsid = EmptyAsNullCharField(read_only=True)

    class Meta:
        model = Genotype
        fields = (
            'chromosome',
            'coordinate',
            'ref',
            'alt',
            'gt',
            'rsid',
            'sample',
            'assembly',
            'species',
        )
        read_only_fields = fields


def serialize_genotype(genotype: Genotype) -> dict[str, Any]:
    """Serialize one Genotype to the public API shape."""
    return dict(GenotypeSerializer(genotype).data)


def serialize_genotype_list(genotypes: Iterable[Genotype]) -> dict[str, list[Mapping[str, Any]]]:
    return {
        'genotypes': GenotypeSerializer(genotypes, many=True).data,
    }
