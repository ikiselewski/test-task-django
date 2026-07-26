# test-task-django

## Запуск

```bash
mamba env create -f env.yml
mamba activate test-task-django

wget https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/latest/GRCh38/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz

python manage.py migrate
python manage.py load_vcf HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz
python manage.py runserver
```

## API

```
http://127.0.0.1:8000/api/get_genotypes/?chromosome=chr1&coordinate=1234
```
