"""
Management command: load a VCF (.vcf / .vcf.gz) into the genotype schema.

Examples
--------
# GIAB HG001 benchmark (GRCh38), sample name from VCF header column:
python manage.py load_vcf HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz

# Explicit taxonomy / sample metadata:
python manage.py load_vcf sample.vcf \\
    --sample HG001 \\
    --sample-aliases NA12878 \\
    --assembly GRCh38 \\
    --species "Homo sapiens"

# Re-import replacing previous genotypes for the same sample(s):
python manage.py load_vcf sample.vcf --sample HG001 --replace
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, OperationalError

from api.services import VcfLoadError, VcfLoader


class Command(BaseCommand):
    help = (
        'Load genotypes from a VCF/VCF.GZ file into the normalized schema '
        '(Species, Assembly, Chromosome, Coordinate, Allele, Sample, Genotype).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'vcf_file',
            type=str,
            help='Path to the VCF file (.vcf or .vcf.gz)',
        )
        parser.add_argument(
            '--sample',
            type=str,
            default=None,
            help=(
                'Sample name override. Used when the VCF has no sample column, '
                'or has a single sample column that should be renamed.'
            ),
        )
        parser.add_argument(
            '--sample-aliases',
            type=str,
            default='',
            help='Comma-separated alternate sample IDs (e.g. NA12878).',
        )
        parser.add_argument(
            '--assembly',
            type=str,
            default='GRCh38',
            help='Reference genome assembly name (default: GRCh38).',
        )
        parser.add_argument(
            '--species',
            type=str,
            default='Homo sapiens',
            help='Species scientific name (default: Homo sapiens).',
        )
        parser.add_argument(
            '--species-common-name',
            type=str,
            default='human',
            help='Species common name (default: human).',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=VcfLoader.DEFAULT_BATCH_SIZE,
            help=f'Bulk insert batch size (default: {VcfLoader.DEFAULT_BATCH_SIZE}).',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Delete existing genotypes for the target sample(s) before load.',
        )

    def handle(self, *args, **options):
        vcf_file = options['vcf_file']
        self.stdout.write(self.style.MIGRATE_HEADING(f'Loading {vcf_file}'))
        self.stdout.write(
            f"  species={options['species']!r}  assembly={options['assembly']!r}  "
            f"sample={options['sample']!r}  batch_size={options['batch_size']}"
        )

        def on_progress(count: int, message: str) -> None:
            self.stdout.write(f'  … {message}')

        try:
            loader = VcfLoader(
                vcf_file,
                species_name=options['species'],
                species_common_name=options['species_common_name'],
                assembly_name=options['assembly'],
                sample_name=options['sample'],
                sample_aliases=options['sample_aliases'],
                batch_size=options['batch_size'],
                replace_sample=options['replace'],
                progress=on_progress,
            )
            stats = loader.load()
        except VcfLoadError as exc:
            raise CommandError(str(exc)) from exc
        except OSError as exc:
            raise CommandError(f'Cannot read VCF: {exc}') from exc
        except OperationalError as exc:
            raise CommandError(
                f'Database schema is missing or outdated ({exc}). '
                'Run: python manage.py migrate'
            ) from exc
        except DatabaseError as exc:
            raise CommandError(f'Database error while loading VCF: {exc}') from exc

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Load complete'))
        self.stdout.write(f'  variants read     : {stats.variants_read}')
        self.stdout.write(f'  genotypes created : {stats.genotypes_created}')
        self.stdout.write(f'  samples           : {", ".join(stats.samples) or "—"}')
        self.stdout.write(f'  assembly          : {stats.assembly}')
        self.stdout.write(f'  species           : {stats.species}')
