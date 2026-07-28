from django.db import IntegrityError
from django.test import TestCase

from api.models import (
    Allele,
    Assembly,
    Chromosome,
    Coordinate,
    Genotype,
    Sample,
    Species,
)


class ModelGraphTests(TestCase):
    def setUp(self):
        self.species = Species.objects.create(name='Homo sapiens', common_name='human')
        self.assembly = Assembly.objects.create(species=self.species, name='GRCh38')
        self.chrom = Chromosome.objects.create(assembly=self.assembly, name='chr1')
        self.coord = Coordinate.objects.create(chromosome=self.chrom, position=100)
        self.ref = Allele.objects.create(sequence='A')
        self.alt = Allele.objects.create(sequence='G')
        self.sample = Sample.objects.create(species=self.species, name='HG001')

    def test_coordinate_unique_per_chromosome(self):
        with self.assertRaises(IntegrityError):
            Coordinate.objects.create(chromosome=self.chrom, position=100)

    def test_genotype_unique_per_sample_coordinate(self):
        Genotype.objects.create(
            sample=self.sample,
            coordinate=self.coord,
            ref_allele=self.ref,
            alt='G',
            gt='0/1',
        )
        with self.assertRaises(IntegrityError):
            Genotype.objects.create(
                sample=self.sample,
                coordinate=self.coord,
                ref_allele=self.ref,
                alt='G',
                gt='1/1',
            )

    def test_same_coordinate_different_samples_allowed(self):
        other = Sample.objects.create(species=self.species, name='HG002')
        Genotype.objects.create(
            sample=self.sample,
            coordinate=self.coord,
            ref_allele=self.ref,
            alt='G',
            gt='0/1',
        )
        Genotype.objects.create(
            sample=other,
            coordinate=self.coord,
            ref_allele=self.ref,
            alt='G',
            gt='1/1',
        )
        self.assertEqual(Genotype.objects.filter(coordinate=self.coord).count(), 2)

    def test_assembly_is_species_scoped(self):
        mouse = Species.objects.create(name='Mus musculus')
        Assembly.objects.create(species=mouse, name='GRCh38')  # same name, different species
        self.assertEqual(Assembly.objects.filter(name='GRCh38').count(), 2)
