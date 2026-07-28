# Generated for normalized genotype schema

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Allele',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence', models.CharField(help_text='Allele sequence exactly as in VCF REF/ALT.', max_length=512, unique=True)),
            ],
            options={
                'ordering': ['sequence'],
            },
        ),
        migrations.CreateModel(
            name='Species',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Display name, typically the scientific name.', max_length=100, unique=True)),
                ('common_name', models.CharField(blank=True, default='', max_length=100)),
            ],
            options={
                'verbose_name_plural': 'species',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Assembly',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Assembly name, e.g. GRCh38, GRCh37, T2T-CHM13.', max_length=50)),
                ('accession', models.CharField(blank=True, default='', help_text='Optional accession (e.g. GCA_000001405.15).', max_length=64)),
                ('description', models.TextField(blank=True, default='')),
                ('species', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assemblies', to='api.species')),
            ],
            options={
                'verbose_name_plural': 'assemblies',
                'ordering': ['species__name', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Chromosome',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, help_text='Contig name as in VCF CHROM (chr1, 1, chrX, …).', max_length=50)),
                ('length', models.PositiveBigIntegerField(blank=True, help_text='Optional contig length from ##contig header.', null=True)),
                ('assembly', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chromosomes', to='api.assembly')),
            ],
            options={
                'ordering': ['assembly__name', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Coordinate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveIntegerField(help_text='1-based position (VCF POS).')),
                ('chromosome', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coordinates', to='api.chromosome')),
            ],
            options={
                'ordering': ['chromosome__name', 'position'],
            },
        ),
        migrations.CreateModel(
            name='Sample',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Primary identifier (e.g. HG001).', max_length=100)),
                ('aliases', models.CharField(blank=True, default='', help_text='Comma-separated alternate IDs (e.g. NA12878).', max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('species', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='samples', to='api.species')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Genotype',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gt', models.CharField(blank=True, default='', help_text='Genotype string from FORMAT/GT (e.g. 0/1, 1|1).', max_length=32)),
                ('rsid', models.CharField(blank=True, default='', help_text='Variant identifier from VCF ID column when present.', max_length=64)),
                ('alt', models.CharField(help_text='Alternate allele(s) as in VCF (comma-separated if multi-allelic).', max_length=512)),
                ('coordinate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='genotypes', to='api.coordinate')),
                ('ref_allele', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='genotypes_as_ref', to='api.allele')),
                ('sample', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='genotypes', to='api.sample')),
            ],
            options={
                'verbose_name': 'genotype',
                'verbose_name_plural': 'genotypes',
                'ordering': ['coordinate__chromosome__name', 'coordinate__position'],
            },
        ),
        migrations.CreateModel(
            name='GenotypeAltAllele',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('index', models.PositiveSmallIntegerField()),
                ('allele', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='genotype_alt_links', to='api.allele')),
                ('genotype', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alt_allele_links', to='api.genotype')),
            ],
            options={
                'ordering': ['genotype_id', 'index'],
            },
        ),
        migrations.AddField(
            model_name='genotype',
            name='alt_alleles',
            field=models.ManyToManyField(blank=True, related_name='genotypes_as_alt', through='api.GenotypeAltAllele', to='api.allele'),
        ),
        migrations.AddConstraint(
            model_name='assembly',
            constraint=models.UniqueConstraint(fields=('species', 'name'), name='uniq_assembly_per_species'),
        ),
        migrations.AddConstraint(
            model_name='chromosome',
            constraint=models.UniqueConstraint(fields=('assembly', 'name'), name='uniq_chromosome_per_assembly'),
        ),
        migrations.AddConstraint(
            model_name='coordinate',
            constraint=models.UniqueConstraint(fields=('chromosome', 'position'), name='uniq_coordinate_on_chromosome'),
        ),
        migrations.AddIndex(
            model_name='coordinate',
            index=models.Index(fields=['chromosome', 'position'], name='api_coordin_chromos_idx'),
        ),
        migrations.AddConstraint(
            model_name='sample',
            constraint=models.UniqueConstraint(fields=('species', 'name'), name='uniq_sample_per_species'),
        ),
        migrations.AddConstraint(
            model_name='genotype',
            constraint=models.UniqueConstraint(fields=('sample', 'coordinate'), name='uniq_genotype_per_sample_coordinate'),
        ),
        migrations.AddIndex(
            model_name='genotype',
            index=models.Index(fields=['sample', 'coordinate'], name='api_genotyp_sample_coord_idx'),
        ),
        migrations.AddConstraint(
            model_name='genotypealtallele',
            constraint=models.UniqueConstraint(fields=('genotype', 'index'), name='uniq_alt_index_per_genotype'),
        ),
        migrations.AddConstraint(
            model_name='genotypealtallele',
            constraint=models.UniqueConstraint(fields=('genotype', 'allele'), name='uniq_alt_allele_per_genotype'),
        ),
    ]
