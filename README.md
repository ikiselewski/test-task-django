# Genotype API (Django test task)

HTTP API and management tooling for loading **VCF** genotypes into SQLite and
querying them by chromosome / genomic position.

Built with **Django 5.1** and **Python 3.11**.

---

## Quick start

```bash
mamba env create -f env.yml
mamba activate test-task-django

# Optional: full GIAB HG001 benchmark (~GRCh38)
wget https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/latest/GRCh38/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz

python manage.py migrate
python manage.py load_vcf HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz \
  --sample HG001 \
  --sample-aliases NA12878 \
  --assembly GRCh38 \
  --species "Homo sapiens"

# Or load the tiny demo file shipped in the repo:
# python manage.py load_vcf sample.vcf --sample HG001 --sample-aliases NA12878

python manage.py runserver
```

Query in the browser:

```
http://127.0.0.1:8000/api/get_genotypes/?chromosome=chr1&coordinate=1234
```

---

## What was implemented

| Requirement | Implementation |
|---|---|
| Download / use GIAB VCF | Documented + `load_vcf` accepts `.vcf` / `.vcf.gz` |
| Model for genotype data | Normalized graph (bonus), not a single flat table |
| `manage.py load_vcf <file>` | Bulk loader with taxonomy + sample options |
| `GET /api/get_genotypes/` | **Class-based** `GenotypeListView` + filters |
| SQLite | Default Django DB |
| Bonus multi-sample biology models | Species → Assembly → Chromosome → Coordinate, Allele, Sample, Genotype |

---

## Domain model (biology)

A VCF row is not “just five columns”. It is a **genotype call** that only makes
sense inside a reference context and for a specific individual:

```
Species  ──►  Assembly  ──►  Chromosome  ──►  Coordinate (1-based POS)
   │                                                ▲
   └──►  Sample (e.g. HG001 / NA12878)              │
              │                                     │
              └──────────►  Genotype  ──────────────┘
                              │  ref_allele → Allele
                              │  alt_alleles → Allele (ordered, multi-allelic)
                              └── gt (VCF GT: 0/1, 1/1, 1|2, …)
```

### Why these entities

| Model | Biological meaning |
|---|---|
| **Species** | Organism. Assemblies and samples belong to a species (`Homo sapiens`). |
| **Assembly** | Reference genome build. **Coordinates are assembly-specific**: `chr1:1234` in GRCh38 ≠ `chr1:1234` in GRCh37. GIAB HG001 benchmark is against **GRCh38**. |
| **Chromosome** | Contig of an assembly (`chr1`…`chr22`, `chrX`, `chrY`, `chrM`). Length can come from `##contig` headers. |
| **Coordinate** | 1-based genomic position (VCF `POS`) on a chromosome. Shared by all samples that have a call there. |
| **Allele** | DNA sequence used as REF or ALT. Stored once and reused (SNVs and indels). |
| **Sample** | Individual / specimen. **Multiple VCFs from different people** → multiple `Sample` rows (e.g. HG001, HG002). HG001 ≡ Coriell **NA12878**. |
| **Genotype** | Call for one sample at one coordinate: REF allele, ALT allele(s), and **GT**. |

### VCF GT encoding (brief)

Allele indices in `GT` refer to the list `[REF] + ALT.split(",")`:

- `0` — reference allele  
- `1` — first alternate  
- `2` — second alternate, …  
- `/` — unphased, `|` — phased  

Examples: `0/1` heterozygous REF/ALT1, `1/1` homozygous ALT1, `1/2` heterozygous ALT1/ALT2.

The loader extracts `GT` from the `FORMAT` column correctly (e.g. `GT:GQ` + `0/1:99` → `0/1`), instead of taking the last tab field blindly.

---

## API

**Class-based view:** `api.views.GenotypeListView` (`django.views.View`).

```
GET /api/get_genotypes/
```

| Query param | Required | Description |
|---|---|---|
| `chromosome` | no | Exact contig name (`chr1`) |
| `coordinate` | no | Exact 1-based position (integer; non-integers ignored) |
| `sample` | no | Sample name (`HG001`) |
| `assembly` | no | Assembly name (`GRCh38`) |

### Example response

```json
{
  "genotypes": [
    {
      "chromosome": "chr1",
      "coordinate": 1234,
      "ref": "A",
      "alt": "T",
      "gt": "0/1",
      "rsid": "rs1",
      "sample": "HG001",
      "assembly": "GRCh38",
      "species": "Homo sapiens"
    }
  ]
}
```

OpenAPI description: [`docs/schema/openapi.yaml`](docs/schema/openapi.yaml).

---

## `load_vcf` options

```bash
python manage.py load_vcf path/to/file.vcf.gz \
  --sample HG001 \
  --sample-aliases NA12878 \
  --assembly GRCh38 \
  --species "Homo sapiens" \
  --batch-size 5000 \
  --replace
```

| Flag | Purpose |
|---|---|
| `--sample` | Override / set sample name when header has no (or one) sample column |
| `--sample-aliases` | e.g. `NA12878` |
| `--assembly` | Reference assembly (default `GRCh38`) |
| `--species` | Species name (default `Homo sapiens`) |
| `--batch-size` | Bulk insert batch size |
| `--replace` | Drop existing genotypes for target sample(s) before reload |

Multi-sample VCFs create one `Genotype` per sample column.

---

## Project layout

```
manage.py
env.yml
sample.vcf                 # tiny multi-allelic demo VCF
docs/
  task_description.md
  schema/openapi.yaml
src/
  config/                  # Django project settings
  api/
    models.py              # normalized biology schema
    views.py               # GenotypeListView (CBV)
    serializers.py
    urls.py
    admin.py
    services/
      vcf_loader.py        # parse + bulk load
      genotype_query.py    # filtered querysets
    management/commands/load_vcf.py
    tests/
```

---

## Tests

```bash
python manage.py test api
```

Covers model constraints, VCF loading (including multi-allelic GT and FORMAT parsing), and the HTTP API filters.

---

## Design notes

1. **Class-based API** — Django’s documented CBV style (`View.as_view()`), not a bare function view.
2. **Normalized schema** — supports many samples / assemblies without duplicating chromosome+position for every row’s free text.
3. **Bulk load** — batched `bulk_create` with coordinate/allele caches so GIAB-scale files are practical on SQLite.
4. **No extra runtime deps** — only what `env.yml` declares (Django + Python). VCF parsing is pure Python (`gzip` + tab split).
