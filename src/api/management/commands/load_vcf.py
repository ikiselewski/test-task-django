import csv
import gzip

from django.core.management.base import BaseCommand

from api.models import Genotype


class Command(BaseCommand):
    help = 'Load VCF data into Genotype model'

    def add_arguments(self, parser):
        parser.add_argument('vcf_file', type=str, help='Path to the VCF file (.vcf or .vcf.gz)')

    def handle(self, *args, **options):
        vcf_file = options['vcf_file']
        self.stdout.write(f'Loading {vcf_file}...')

        if vcf_file.endswith('.gz'):
            file_handle = gzip.open(vcf_file, 'rt')
        else:
            file_handle = open(vcf_file, 'r')

        reader = csv.reader(file_handle, delimiter='\t')

        count = 0
        for row in reader:
            if not row or row[0].startswith('#'):
                continue  # skip header lines
            if len(row) < 9:
                continue
            chrom = row[0]
            pos = int(row[1])
            ref = row[3]
            alt = row[4]
            gt = row[-1] if len(row) > 9 else ''
            Genotype.objects.create(
                chromosome=chrom,
                coordinate=pos,
                ref=ref,
                alt=alt,
                gt=gt,
            )
            count += 1
            if count % 1000 == 0:
                self.stdout.write(f'Loaded {count} genotypes...')

        file_handle.close()
        self.stdout.write(
            self.style.SUCCESS(f'Successfully loaded {count} genotypes from {vcf_file}')
        )
