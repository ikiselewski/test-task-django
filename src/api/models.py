"""
Domain models for genomic genotypes loaded from VCF files.

Biological hierarchy (bonus requirement)
----------------------------------------
A VCF genotype call is only meaningful in context:

    Species  →  Assembly  →  Chromosome  →  Coordinate
                     ↘
    Sample (individual)  →  Genotype (alleles + GT at a coordinate)

Why this shape:
- **Species** — organisms differ (human vs mouse); samples and assemblies
  belong to a species.
- **Assembly** — genomic coordinates are assembly-specific. Position 1234 on
  chr1 in GRCh38 is *not* the same locus as position 1234 on chr1 in GRCh37.
  GIAB HG001 benchmark is called against GRCh38.
- **Chromosome** — contigs of an assembly (chr1..chr22, chrX, chrY, chrM).
- **Coordinate** — 1-based genomic position (VCF POS) on a chromosome.
- **Allele** — DNA sequence observed as REF or ALT; stored once and reused.
- **Sample** — the individual/specimen (e.g. HG001 / NA12878). Multiple VCF
  files from different people become different Sample rows.
- **Genotype** — the call for one sample at one coordinate: which alleles and
  the VCF GT encoding (0/1 heterozygous, 1/1 homozygous ALT, …).
"""

from django.db import models


class Species(models.Model):
    """Biological species (e.g. Homo sapiens)."""

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Display name, typically the scientific name.',
    )
    common_name = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        verbose_name_plural = 'species'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Assembly(models.Model):
    """
    Reference genome assembly.

    VCF POS coordinates are only comparable within the same assembly.
    Example: GRCh38 (hg38) used by the GIAB HG001 benchmark VCF.
    """

    species = models.ForeignKey(
        Species,
        on_delete=models.CASCADE,
        related_name='assemblies',
    )
    name = models.CharField(
        max_length=50,
        help_text='Assembly name, e.g. GRCh38, GRCh37, T2T-CHM13.',
    )
    accession = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='Optional accession (e.g. GCA_000001405.15).',
    )
    description = models.TextField(blank=True, default='')

    class Meta:
        verbose_name_plural = 'assemblies'
        constraints = [
            models.UniqueConstraint(
                fields=['species', 'name'],
                name='uniq_assembly_per_species',
            ),
        ]
        ordering = ['species__name', 'name']

    def __str__(self) -> str:
        return f'{self.name} ({self.species})'


class Chromosome(models.Model):
    """Contig / chromosome belonging to a reference assembly."""

    assembly = models.ForeignKey(
        Assembly,
        on_delete=models.CASCADE,
        related_name='chromosomes',
    )
    name = models.CharField(
        max_length=50,
        help_text='Contig name as in VCF CHROM (chr1, 1, chrX, …).',
        db_index=True,
    )
    length = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text='Optional contig length from ##contig header.',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['assembly', 'name'],
                name='uniq_chromosome_per_assembly',
            ),
        ]
        ordering = ['assembly__name', 'name']

    def __str__(self) -> str:
        return f'{self.name} @ {self.assembly.name}'


class Coordinate(models.Model):
    """
    1-based genomic position on a chromosome (VCF POS column).

    Separated from alleles so the same locus can be referenced by many
    samples and by multiple alternate alleles without duplicating position.
    """

    chromosome = models.ForeignKey(
        Chromosome,
        on_delete=models.CASCADE,
        related_name='coordinates',
    )
    position = models.PositiveIntegerField(
        help_text='1-based position (VCF POS).',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['chromosome', 'position'],
                name='uniq_coordinate_on_chromosome',
            ),
        ]
        indexes = [
            models.Index(fields=['chromosome', 'position']),
        ]
        ordering = ['chromosome__name', 'position']

    def __str__(self) -> str:
        return f'{self.chromosome.name}:{self.position}'


class Allele(models.Model):
    """
    DNA sequence allele (bases A/C/G/T/N and indels).

    REF and ALT values from VCF are stored here once and shared. Multi-allelic
    sites reference several Allele rows via Genotype.alt_alleles.
    """

    sequence = models.CharField(
        max_length=512,
        unique=True,
        help_text='Allele sequence exactly as in VCF REF/ALT.',
    )

    class Meta:
        ordering = ['sequence']

    def __str__(self) -> str:
        if len(self.sequence) <= 20:
            return self.sequence
        return f'{self.sequence[:17]}…'


class Sample(models.Model):
    """
    Biological sample / individual.

    Enables loading many VCF files from different people. GIAB HG001 is the
    same individual as Coriell NA12878.
    """

    species = models.ForeignKey(
        Species,
        on_delete=models.CASCADE,
        related_name='samples',
    )
    name = models.CharField(
        max_length=100,
        help_text='Primary identifier (e.g. HG001).',
    )
    aliases = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Comma-separated alternate IDs (e.g. NA12878).',
    )
    description = models.TextField(blank=True, default='')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['species', 'name'],
                name='uniq_sample_per_species',
            ),
        ]
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Genotype(models.Model):
    """
    Genotype call for one sample at one genomic coordinate.

    VCF GT encoding
    ---------------
    Allele indices in GT refer to the allele list [REF] + ALT split by comma:
      0 = reference allele
      1 = first alternate allele
      2 = second alternate allele, …
    Separators: ``/`` unphased, ``|`` phased.
    Examples: ``0/1`` heterozygous, ``1/1`` homozygous ALT, ``0|1`` phased het.
    """

    sample = models.ForeignKey(
        Sample,
        on_delete=models.CASCADE,
        related_name='genotypes',
    )
    coordinate = models.ForeignKey(
        Coordinate,
        on_delete=models.CASCADE,
        related_name='genotypes',
    )
    ref_allele = models.ForeignKey(
        Allele,
        on_delete=models.PROTECT,
        related_name='genotypes_as_ref',
    )
    # Ordered ALT alleles (index 0 → GT allele 1, index 1 → GT allele 2, …)
    alt_alleles = models.ManyToManyField(
        Allele,
        through='GenotypeAltAllele',
        related_name='genotypes_as_alt',
        blank=True,
    )
    gt = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text='Genotype string from FORMAT/GT (e.g. 0/1, 1|1).',
    )
    rsid = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='Variant identifier from VCF ID column when present.',
    )
    # Denormalized ALT string for fast API responses (matches VCF ALT column)
    alt = models.CharField(
        max_length=512,
        help_text='Alternate allele(s) as in VCF (comma-separated if multi-allelic).',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['sample', 'coordinate'],
                name='uniq_genotype_per_sample_coordinate',
            ),
        ]
        indexes = [
            models.Index(fields=['sample', 'coordinate']),
        ]
        verbose_name = 'genotype'
        verbose_name_plural = 'genotypes'
        ordering = ['coordinate__chromosome__name', 'coordinate__position']

    def __str__(self) -> str:
        return (
            f'{self.sample.name} '
            f'{self.coordinate} {self.ref_allele.sequence}/{self.alt} GT={self.gt}'
        )

    @property
    def chromosome_name(self) -> str:
        return self.coordinate.chromosome.name

    @property
    def position(self) -> int:
        return self.coordinate.position

    @property
    def ref(self) -> str:
        return self.ref_allele.sequence


class GenotypeAltAllele(models.Model):
    """
    Through table preserving ALT allele order for multi-allelic sites.

    ``index`` is 0-based position in the VCF ALT list (GT allele number = index + 1).
    """

    genotype = models.ForeignKey(
        Genotype,
        on_delete=models.CASCADE,
        related_name='alt_allele_links',
    )
    allele = models.ForeignKey(
        Allele,
        on_delete=models.PROTECT,
        related_name='genotype_alt_links',
    )
    index = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['genotype', 'index'],
                name='uniq_alt_index_per_genotype',
            ),
            models.UniqueConstraint(
                fields=['genotype', 'allele'],
                name='uniq_alt_allele_per_genotype',
            ),
        ]
        ordering = ['genotype_id', 'index']

    def __str__(self) -> str:
        return f'{self.genotype_id} alt[{self.index}]={self.allele.sequence}'
