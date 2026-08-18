from django.test import TestCase
from rest_framework import serializers

from api.models import (
    Allele,
    Assembly,
    Chromosome,
    Coordinate,
    Genotype,
    Sample,
    Species,
)
from api.serializers import GenotypeSerializer, serialize_genotype_list


class GenotypeSerializerTests(TestCase):
    def setUp(self):
        species = Species.objects.create(name='Homo sapiens', common_name='human')
        assembly = Assembly.objects.create(species=species, name='GRCh38')
        chrom = Chromosome.objects.create(assembly=assembly, name='chr1')
        coord = Coordinate.objects.create(chromosome=chrom, position=1234)
        ref = Allele.objects.create(sequence='A')
        self.sample = Sample.objects.create(species=species, name='HG001')
        self.genotype = Genotype.objects.create(
            sample=self.sample,
            coordinate=coord,
            ref_allele=ref,
            alt='T',
            gt='0/1',
            rsid='rs1',
        )

    def test_is_model_serializer(self):
        self.assertTrue(issubclass(GenotypeSerializer, serializers.ModelSerializer))
        self.assertIs(GenotypeSerializer.Meta.model, Genotype)

    def test_serializes_openapi_shape(self):
        data = GenotypeSerializer(self.genotype).data
        self.assertEqual(
            dict(data),
            {
                'chromosome': 'chr1',
                'coordinate': 1234,
                'ref': 'A',
                'alt': 'T',
                'gt': '0/1',
                'rsid': 'rs1',
                'sample': 'HG001',
                'assembly': 'GRCh38',
                'species': 'Homo sapiens',
            },
        )

    def test_blank_gt_and_rsid_become_null(self):
        self.genotype.gt = ''
        self.genotype.rsid = ''
        self.genotype.save()

        data = GenotypeSerializer(self.genotype).data
        self.assertIsNone(data['gt'])
        self.assertIsNone(data['rsid'])

    def test_list_wrapper_uses_model_serializer(self):
        payload = serialize_genotype_list([self.genotype])
        self.assertEqual(list(payload.keys()), ['genotypes'])
        self.assertEqual(len(payload['genotypes']), 1)
        self.assertEqual(payload['genotypes'][0]['chromosome'], 'chr1')
        self.assertEqual(payload['genotypes'][0]['coordinate'], 1234)
