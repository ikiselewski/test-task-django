# Genotype API

## Быстрый старт

```bash
mamba env create -f env.yml
mamba activate test-task-django

wget https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/latest/GRCh38/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz

python manage.py migrate
python manage.py load_vcf HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz \
  --sample HG001 \
  --sample-aliases NA12878 \
  --assembly GRCh38 \
  --species "Homo sapiens"

python manage.py runserver
```

Запрос:

```
http://127.0.0.1:8000/api/get_genotypes/?chromosome=chr1&coordinate=1234
```

## Доменная модель

Вызов генотипа из VCF имеет смысл только в контексте референсного генома и конкретного образца:

```
Species  ──►  Assembly  ──►  Chromosome  ──►  Coordinate (POS, 1-based)
   │                                               ▲
   └──►  Sample (например HG001 / NA12878)         │
              │                                    │
              └──────────►  Genotype  ─────────────┘
                              │  ref_allele → Allele
                              │  alt_alleles → Allele (порядок ALT)
                              └── gt (0/1, 1/1, 1|2, …)
```

| Модель | Смысл |
|---|---|
| **Species** | Биологический вид (`Homo sapiens`). К нему привязаны сборки и образцы. |
| **Assembly** | Референсный геном (сборка). Координаты **зависят от сборки**: `chr1:1234` в GRCh38 ≠ `chr1:1234` в GRCh37. Бенчмарк GIAB HG001 — против **GRCh38**. |
| **Chromosome** | Контиг / хромосома сборки (`chr1`…`chr22`, `chrX`, `chrY`, `chrM`). |
| **Coordinate** | 1-based позиция (колонка VCF `POS`) на хромосоме. Одна точка для всех образцов. |
| **Allele** | Последовательность ДНК (REF или ALT). Хранится один раз и переиспользуется. |
| **Sample** | Индивид / образец. Несколько VCF от разных людей → несколько `Sample` (HG001, HG002). HG001 = Coriell **NA12878**. |
| **Genotype** | Вызов для одного образца в одной координате: REF, ALT(ы) и **GT**. |

**GT (кратко):** индексы аллелей — `[REF] + ALT.split(",")` (`0` = REF, `1` = первый ALT, …). `/` — без фазы, `|` — с фазой. Примеры: `0/1` гетерозигота, `1/1` гомозигота ALT, `1/2` два разных ALT.
