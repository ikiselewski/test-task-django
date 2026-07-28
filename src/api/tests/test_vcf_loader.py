from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from api.models import (
    Allele,
    Assembly,
    Chromosome,
    Coordinate,
    Genotype,
    GenotypeAltAllele,
    Sample,
    Species,
)
from api.services.vcf_loader import VcfLoader


REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_VCF = REPO_ROOT / 'sample.vcf'


class VcfLoaderTests(TestCase):
    def test_load_sample_vcf_builds_full_graph(self):
        stats = VcfLoader(
            SAMPLE_VCF,
            sample_name='HG001',
            sample_aliases='NA12878',
            assembly_name='GRCh38',
            species_name='Homo sapiens',
        ).load()

        self.assertEqual(stats.variants_read, 4)
        self.assertEqual(stats.genotypes_created, 4)
        self.assertEqual(stats.samples, ['HG001'])

        self.assertTrue(Species.objects.filter(name='Homo sapiens').exists())
        self.assertTrue(Assembly.objects.filter(name='GRCh38').exists())
        self.assertEqual(Chromosome.objects.count(), 2)
        self.assertEqual(Coordinate.objects.count(), 4)
        self.assertEqual(Sample.objects.get().aliases, 'NA12878')

        # REF/ALT alleles are shared, not duplicated as free text only
        self.assertTrue(Allele.objects.filter(sequence='A').exists())
        self.assertTrue(Allele.objects.filter(sequence='T').exists())

        het = Genotype.objects.get(
            coordinate__chromosome__name='chr1',
            coordinate__position=1234,
        )
        self.assertEqual(het.gt, '0/1')
        self.assertEqual(het.ref_allele.sequence, 'A')
        self.assertEqual(het.alt, 'T')
        self.assertEqual(het.rsid, 'rs1')
        self.assertEqual(het.alt_allele_links.count(), 1)

        # Multi-allelic site: ALT=A,T → two ordered alt alleles, GT=1/2
        multi = Genotype.objects.get(
            coordinate__chromosome__name='chr22',
            coordinate__position=10000,
        )
        self.assertEqual(multi.gt, '1/2')
        self.assertEqual(multi.alt, 'A,T')
        alts = list(
            GenotypeAltAllele.objects.filter(genotype=multi)
            .order_by('index')
            .values_list('allele__sequence', flat=True)
        )
        self.assertEqual(alts, ['A', 'T'])

        # Indel
        indel = Genotype.objects.get(
            coordinate__chromosome__name='chr1',
            coordinate__position=2000,
        )
        self.assertEqual(indel.ref_allele.sequence, 'AT')
        self.assertEqual(indel.alt, 'A')

    def test_extract_gt_from_format(self):
        self.assertEqual(VcfLoader.extract_gt('GT:GQ:DP', '0/1:99:30'), '0/1')
        self.assertEqual(VcfLoader.extract_gt('GQ:GT', '12:1|1'), '1|1')
        self.assertEqual(VcfLoader.extract_gt('GT', '.'), '')
        self.assertEqual(VcfLoader.extract_gt('GT', './.'), '')

    def test_management_command(self):
        call_command(
            'load_vcf',
            str(SAMPLE_VCF),
            sample='HG001',
            assembly='GRCh38',
            species='Homo sapiens',
        )
        self.assertEqual(Genotype.objects.count(), 4)

    def test_replace_reloads_cleanly(self):
        VcfLoader(SAMPLE_VCF, sample_name='HG001').load()
        self.assertEqual(Genotype.objects.count(), 4)

        stats = VcfLoader(SAMPLE_VCF, sample_name='HG001', replace_sample=True).load()
        self.assertEqual(stats.genotypes_created, 4)
        self.assertEqual(Genotype.objects.count(), 4)
