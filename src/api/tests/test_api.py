from pathlib import Path
from unittest.mock import patch

from django.db import OperationalError
from django.test import Client, TestCase

from api.services.vcf_loader import VcfLoader


REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_VCF = REPO_ROOT / 'sample.vcf'


class GenotypeApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        VcfLoader(
            SAMPLE_VCF,
            sample_name='HG001',
            assembly_name='GRCh38',
            species_name='Homo sapiens',
        ).load()

    def setUp(self):
        self.client = Client()

    def test_list_all(self):
        response = self.client.get('/api/get_genotypes/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('genotypes', data)
        self.assertEqual(len(data['genotypes']), 4)

    def test_filter_chromosome_and_coordinate(self):
        response = self.client.get(
            '/api/get_genotypes/',
            {'chromosome': 'chr1', 'coordinate': '1234'},
        )
        self.assertEqual(response.status_code, 200)
        genotypes = response.json()['genotypes']
        self.assertEqual(len(genotypes), 1)
        g = genotypes[0]
        self.assertEqual(g['chromosome'], 'chr1')
        self.assertEqual(g['coordinate'], 1234)
        self.assertEqual(g['ref'], 'A')
        self.assertEqual(g['alt'], 'T')
        self.assertEqual(g['gt'], '0/1')
        self.assertEqual(g['sample'], 'HG001')
        self.assertEqual(g['assembly'], 'GRCh38')
        self.assertEqual(g['species'], 'Homo sapiens')

    def test_filter_chromosome_only(self):
        response = self.client.get('/api/get_genotypes/', {'chromosome': 'chr1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['genotypes']), 3)

    def test_invalid_coordinate_returns_400(self):
        response = self.client.get(
            '/api/get_genotypes/',
            {'chromosome': 'chr1', 'coordinate': 'not-an-int'},
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body['error'], 'Invalid query parameters')
        self.assertIn('coordinate', body['details'])

    def test_non_positive_coordinate_returns_400(self):
        response = self.client.get(
            '/api/get_genotypes/',
            {'coordinate': '0'},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('coordinate', response.json()['details'])

    def test_empty_chromosome_returns_400(self):
        response = self.client.get(
            '/api/get_genotypes/',
            {'chromosome': '   '},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('chromosome', response.json()['details'])

    def test_filter_sample_and_assembly(self):
        response = self.client.get(
            '/api/get_genotypes/',
            {'sample': 'HG001', 'assembly': 'GRCh38', 'chromosome': 'chr22'},
        )
        self.assertEqual(response.status_code, 200)
        genotypes = response.json()['genotypes']
        self.assertEqual(len(genotypes), 1)
        self.assertEqual(genotypes[0]['alt'], 'A,T')
        self.assertEqual(genotypes[0]['gt'], '1/2')

    def test_empty_result(self):
        response = self.client.get(
            '/api/get_genotypes/',
            {'chromosome': 'chr1', 'coordinate': '999999'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'genotypes': []})

    def test_post_not_allowed(self):
        response = self.client.post('/api/get_genotypes/')
        self.assertEqual(response.status_code, 405)

    def test_missing_table_returns_503(self):
        with patch(
            'api.views.serialize_genotype_list',
            side_effect=OperationalError('no such table: api_coordinate'),
        ):
            response = self.client.get('/api/get_genotypes/')
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body['error'], 'Database not ready')
        self.assertIn('migrate', body['detail'])
