"""
VCF parser and bulk loader into the normalized genotype schema.

Handles:
- plain .vcf and gzip-compressed .vcf.gz
- ##meta headers (fileformat, reference, contig)
- sample column names on the #CHROM header line
- multi-sample VCFs (one Genotype row per sample column)
- correct GT extraction from FORMAT (not “last column blindly”)
- multi-allelic ALT sites
- batched inserts for multi-million-row GIAB files
"""

from __future__ import annotations

import gzip
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, TextIO

from django.db import transaction

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

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], None]


class VcfLoadError(Exception):
    """Raised when a VCF cannot be parsed or loaded."""


@dataclass
class VcfHeader:
    fileformat: str = ''
    reference: str = ''
    contigs: dict[str, int | None] = field(default_factory=dict)
    sample_names: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)


@dataclass
class VcfLoadStats:
    variants_read: int = 0
    genotypes_created: int = 0
    genotypes_skipped: int = 0
    samples: list[str] = field(default_factory=list)
    assembly: str = ''
    species: str = ''


class VcfLoader:
    """
    Load one VCF file into Species / Assembly / Chromosome / Coordinate /
    Allele / Sample / Genotype.
    """

    DEFAULT_BATCH_SIZE = 5_000

    def __init__(
        self,
        path: str | Path,
        *,
        species_name: str = 'Homo sapiens',
        species_common_name: str = 'human',
        assembly_name: str = 'GRCh38',
        sample_name: str | None = None,
        sample_aliases: str = '',
        batch_size: int = DEFAULT_BATCH_SIZE,
        replace_sample: bool = False,
        progress: ProgressCallback | None = None,
    ) -> None:
        self.path = Path(path)
        self.species_name = species_name
        self.species_common_name = species_common_name
        self.assembly_name = assembly_name
        self.sample_name_override = sample_name
        self.sample_aliases = sample_aliases
        self.batch_size = batch_size
        self.replace_sample = replace_sample
        self.progress = progress or (lambda _n, _msg: None)

        if not self.path.exists():
            raise VcfLoadError(f'VCF file not found: {self.path}')

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def load(self) -> VcfLoadStats:
        stats = VcfLoadStats(
            assembly=self.assembly_name,
            species=self.species_name,
        )

        with self._open() as handle:
            header = self._parse_header(handle)
            samples = self._resolve_samples(header)
            stats.samples = [s.name for s in samples]

            species, assembly = self._ensure_taxonomy()
            # Re-bind samples to the ensured species
            samples = self._ensure_samples(species, samples)

            if self.replace_sample:
                deleted, _ = Genotype.objects.filter(sample__in=samples).delete()
                logger.info('Removed %s existing genotype rows for samples %s', deleted, stats.samples)

            self._load_records(handle, header, assembly, samples, stats)

        return stats

    # ------------------------------------------------------------------
    # IO / header
    # ------------------------------------------------------------------

    def _open(self) -> TextIO:
        if self.path.name.endswith('.gz') or self.path.suffix == '.gz':
            return gzip.open(self.path, 'rt', encoding='utf-8', errors='replace')
        return open(self.path, 'r', encoding='utf-8', errors='replace')

    def _parse_header(self, handle: TextIO) -> VcfHeader:
        header = VcfHeader()
        for line in handle:
            line = line.rstrip('\n')
            if not line:
                continue
            if line.startswith('##'):
                self._parse_meta_line(line, header)
                continue
            if line.startswith('#CHROM'):
                cols = line[1:].split('\t')  # drop leading '#'
                # Standard: CHROM POS ID REF ALT QUAL FILTER INFO FORMAT [SAMPLE...]
                header.columns = cols
                if len(cols) > 9:
                    header.sample_names = cols[9:]
                elif len(cols) == 9:
                    # FORMAT present, no sample columns — allowed but GT will be empty
                    header.sample_names = []
                else:
                    header.sample_names = []
                return header
            # data line before #CHROM — malformed
            raise VcfLoadError('Malformed VCF: data rows before #CHROM header')

        raise VcfLoadError('Malformed VCF: missing #CHROM header line')

    @staticmethod
    def _parse_meta_line(line: str, header: VcfHeader) -> None:
        # ##fileformat=VCFv4.2
        if line.startswith('##fileformat='):
            header.fileformat = line.split('=', 1)[1]
            return
        # ##reference=GRCh38 or ##reference=file://...
        if line.startswith('##reference='):
            header.reference = line.split('=', 1)[1]
            return
        # ##contig=<ID=chr1,length=248956422>
        if line.startswith('##contig='):
            body = line[len('##contig='):].strip('<>')
            parts = {}
            for token in body.split(','):
                if '=' in token:
                    k, v = token.split('=', 1)
                    parts[k] = v
            contig_id = parts.get('ID')
            if contig_id:
                length = int(parts['length']) if 'length' in parts and parts['length'].isdigit() else None
                header.contigs[contig_id] = length

    def _resolve_samples(self, header: VcfHeader) -> list[Sample]:
        """
        Decide Sample names for this load.

        Priority:
        1. --sample CLI override (single sample; if VCF has one column, map to it;
           if multiple columns, still one logical sample name only when override set
           and VCF has exactly one sample column — otherwise use VCF names).
        2. Sample column names from #CHROM.
        3. Fallback synthetic name from filename.
        """
        # Return lightweight placeholders; _ensure_samples attaches FKs.
        names: list[str]
        if header.sample_names:
            names = list(header.sample_names)
            if self.sample_name_override and len(names) == 1:
                names = [self.sample_name_override]
        elif self.sample_name_override:
            names = [self.sample_name_override]
        else:
            names = [self.path.stem.replace('.vcf', '')]

        return [Sample(name=n, aliases=self.sample_aliases if i == 0 else '') for i, n in enumerate(names)]

    # ------------------------------------------------------------------
    # taxonomy / caches
    # ------------------------------------------------------------------

    def _ensure_taxonomy(self) -> tuple[Species, Assembly]:
        species, _ = Species.objects.get_or_create(
            name=self.species_name,
            defaults={'common_name': self.species_common_name},
        )
        assembly, _ = Assembly.objects.get_or_create(
            species=species,
            name=self.assembly_name,
            defaults={
                'description': f'Reference assembly for VCF load of {self.path.name}',
            },
        )
        return species, assembly

    def _ensure_samples(self, species: Species, placeholders: list[Sample]) -> list[Sample]:
        result: list[Sample] = []
        for ph in placeholders:
            sample, created = Sample.objects.get_or_create(
                species=species,
                name=ph.name,
                defaults={
                    'aliases': ph.aliases,
                    'description': f'Loaded from {self.path.name}',
                },
            )
            if not created and ph.aliases and not sample.aliases:
                sample.aliases = ph.aliases
                sample.save(update_fields=['aliases'])
            result.append(sample)
        return result

    def _chromosome_cache(self, assembly: Assembly, header: VcfHeader) -> dict[str, Chromosome]:
        cache: dict[str, Chromosome] = {
            c.name: c for c in Chromosome.objects.filter(assembly=assembly)
        }
        # Prefill from ##contig if present
        for name, length in header.contigs.items():
            if name not in cache:
                chrom, _ = Chromosome.objects.get_or_create(
                    assembly=assembly,
                    name=name,
                    defaults={'length': length},
                )
                cache[name] = chrom
        return cache

    def _get_chromosome(
        self,
        cache: dict[str, Chromosome],
        assembly: Assembly,
        name: str,
    ) -> Chromosome:
        chrom = cache.get(name)
        if chrom is not None:
            return chrom
        chrom, _ = Chromosome.objects.get_or_create(assembly=assembly, name=name)
        cache[name] = chrom
        return chrom

    def _allele_cache(self) -> dict[str, Allele]:
        return {a.sequence: a for a in Allele.objects.all()}

    def _get_allele(self, cache: dict[str, Allele], sequence: str) -> Allele:
        allele = cache.get(sequence)
        if allele is not None:
            return allele
        allele, _ = Allele.objects.get_or_create(sequence=sequence)
        cache[sequence] = allele
        return allele

    # ------------------------------------------------------------------
    # records
    # ------------------------------------------------------------------

    def _load_records(
        self,
        handle: TextIO,
        header: VcfHeader,
        assembly: Assembly,
        samples: list[Sample],
        stats: VcfLoadStats,
    ) -> None:
        chrom_cache = self._chromosome_cache(assembly, header)
        allele_cache = self._allele_cache()

        # Pending bulk rows
        pending_coordinates: dict[tuple[int, int], Coordinate] = {}
        # key: (sample_id, chrom_id, position) → built genotype info
        pending_gt: list[dict] = []
        pending_alt_links: list[tuple[int, int, list[tuple[int, Allele]]]] = []
        # We assign temporary negative PKs? Better approach: flush in stages.

        # Stage strategy:
        # 1. Collect unique (chrom_id, position) and allele sequences per batch
        # 2. bulk_create coordinates / use cache
        # 3. bulk_create genotypes with ignore_conflicts
        # 4. link alt alleles

        batch_rows: list[dict] = []

        for line_no, line in enumerate(handle, start=1):
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue

            row = line.split('\t')
            if len(row) < 5:
                continue

            chrom_name = row[0]
            try:
                position = int(row[1])
            except ValueError:
                logger.warning('Skip line %s: non-integer POS %r', line_no, row[1])
                continue

            rsid = row[2] if row[2] != '.' else ''
            ref_seq = row[3]
            alt_field = row[4]
            if alt_field == '.':
                continue

            format_field = row[8] if len(row) > 8 else 'GT'
            sample_fields = row[9:] if len(row) > 9 else []

            chromosome = self._get_chromosome(chrom_cache, assembly, chrom_name)
            ref_allele = self._get_allele(allele_cache, ref_seq)
            alt_seqs = [a for a in alt_field.split(',') if a and a != '.']
            alt_alleles = [self._get_allele(allele_cache, seq) for seq in alt_seqs]

            # Build per-sample genotype payloads
            if samples and sample_fields:
                pairs = list(zip(samples, sample_fields))
            elif samples and not sample_fields:
                # No sample columns — still store site with empty GT for the
                # declared sample (useful for sites-only VCFs / demos).
                pairs = [(samples[0], '')]
            else:
                continue

            for sample, sample_field in pairs:
                gt = self.extract_gt(format_field, sample_field) if sample_field else ''
                batch_rows.append({
                    'sample': sample,
                    'chromosome': chromosome,
                    'position': position,
                    'ref_allele': ref_allele,
                    'alt_alleles': alt_alleles,
                    'alt': alt_field,
                    'gt': gt,
                    'rsid': rsid,
                })

            stats.variants_read += 1

            if len(batch_rows) >= self.batch_size:
                created = self._flush_batch(batch_rows)
                stats.genotypes_created += created
                batch_rows.clear()
                self.progress(stats.genotypes_created, f'loaded {stats.genotypes_created} genotypes')

        if batch_rows:
            created = self._flush_batch(batch_rows)
            stats.genotypes_created += created
            self.progress(stats.genotypes_created, f'loaded {stats.genotypes_created} genotypes')

    def _flush_batch(self, rows: list[dict]) -> int:
        """
        Persist one batch:
        1. ensure Coordinate rows
        2. bulk_create Genotype (ignore conflicts for re-runs)
        3. bulk_create GenotypeAltAllele links for newly inserted genotypes
        """
        if not rows:
            return 0

        # --- coordinates ---
        coord_keys = {(r['chromosome'].pk, r['position']) for r in rows}
        existing = {
            (c.chromosome_id, c.position): c
            for c in Coordinate.objects.filter(
                chromosome_id__in={k[0] for k in coord_keys},
                position__in={k[1] for k in coord_keys},
            )
        }
        # Filter precisely
        existing = {k: v for k, v in existing.items() if k in coord_keys}

        missing = [
            Coordinate(chromosome_id=cid, position=pos)
            for (cid, pos) in coord_keys
            if (cid, pos) not in existing
        ]
        if missing:
            Coordinate.objects.bulk_create(missing, ignore_conflicts=True)
            # re-fetch
            existing = {
                (c.chromosome_id, c.position): c
                for c in Coordinate.objects.filter(
                    chromosome_id__in={k[0] for k in coord_keys},
                    position__in={k[1] for k in coord_keys},
                )
                if (c.chromosome_id, c.position) in coord_keys
            }

        # --- genotypes ---
        genotype_objs: list[Genotype] = []
        alt_plan: list[tuple[int, int, list[Allele]]] = []  # sample_id, coord_id, alts

        for r in rows:
            coord = existing[(r['chromosome'].pk, r['position'])]
            genotype_objs.append(
                Genotype(
                    sample=r['sample'],
                    coordinate=coord,
                    ref_allele=r['ref_allele'],
                    alt=r['alt'],
                    gt=r['gt'],
                    rsid=r['rsid'],
                )
            )
            alt_plan.append((r['sample'].pk, coord.pk, r['alt_alleles']))

        before_ids = set(
            Genotype.objects.filter(
                sample_id__in={g.sample_id for g in genotype_objs},
                coordinate_id__in={g.coordinate_id for g in genotype_objs},
            ).values_list('sample_id', 'coordinate_id')
        )

        with transaction.atomic():
            Genotype.objects.bulk_create(genotype_objs, ignore_conflicts=True)

            # Fetch genotypes that exist now for this batch (new + old)
            keys = {(s, c) for s, c, _ in alt_plan}
            fetched = {
                (g.sample_id, g.coordinate_id): g
                for g in Genotype.objects.filter(
                    sample_id__in={s for s, _ in keys},
                    coordinate_id__in={c for _, c in keys},
                )
                if (g.sample_id, g.coordinate_id) in keys
            }

            # Only attach ALT links for newly created genotypes
            links: list[GenotypeAltAllele] = []
            created_count = 0
            for sample_id, coord_id, alt_alleles in alt_plan:
                key = (sample_id, coord_id)
                if key in before_ids:
                    continue
                genotype = fetched.get(key)
                if genotype is None:
                    continue
                created_count += 1
                for index, allele in enumerate(alt_alleles):
                    links.append(
                        GenotypeAltAllele(
                            genotype=genotype,
                            allele=allele,
                            index=index,
                        )
                    )
            if links:
                GenotypeAltAllele.objects.bulk_create(links, ignore_conflicts=True)

        return created_count

    # ------------------------------------------------------------------
    # FORMAT / GT helpers
    # ------------------------------------------------------------------

    @staticmethod
    def extract_gt(format_field: str, sample_field: str) -> str:
        """
        Extract GT from a sample column using the FORMAT key list.

        Example: FORMAT=GT:GQ:DP, sample=0/1:99:30 → '0/1'
        """
        if not sample_field or sample_field == '.':
            return ''
        keys = format_field.split(':') if format_field else ['GT']
        values = sample_field.split(':')
        mapping = dict(zip(keys, values))
        gt = mapping.get('GT', '')
        return '' if gt in {'.', './.', '.|.'} else gt
