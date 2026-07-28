"""
Serializers for genotype API responses.

Kept free of DRF so the project stays within the env.yml dependency set
(Django only). Class-based views call these helpers explicitly.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .models import Genotype


def serialize_genotype(genotype: Genotype) -> dict[str, Any]:
    """
    Serialize one Genotype to the public API shape.

    Core fields match the OpenAPI contract (chromosome, coordinate, ref, alt, gt).
    Extra fields expose the normalized biology graph (sample, assembly, species).
    """
    coordinate = genotype.coordinate
    chromosome = coordinate.chromosome
    assembly = chromosome.assembly
    species = assembly.species

    return {
        'chromosome': chromosome.name,
        'coordinate': coordinate.position,
        'ref': genotype.ref_allele.sequence,
        'alt': genotype.alt,
        'gt': genotype.gt or None,
        'rsid': genotype.rsid or None,
        'sample': genotype.sample.name,
        'assembly': assembly.name,
        'species': species.name,
    }


def serialize_genotype_list(genotypes: Iterable[Genotype]) -> dict[str, list[Mapping[str, Any]]]:
    return {
        'genotypes': [serialize_genotype(g) for g in genotypes],
    }
