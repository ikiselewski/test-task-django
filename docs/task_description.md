Тестовое задание
Скачать файл в формате vcf (это обычная текстовая таблица) из проекта GIAB - https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/latest/GRCh38/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz
Создать модель Genotype для загрузки основной информации из vcf файл (хромосома, координата, REF, ALT, GT и тп.)*
Сделать команду load_vcf для manage.py которая получает на вход имя vcf файла и загружает его в модель Genotype (БД mysqlite)
Сделать API endpoint /get_genotypes/ для получения данных из БД с возможностью фильтрации по хромосоме и позиции

* Бонус - сделать несколько моделей и связей между ними с учетом возможности загружать множество vcf файлов от разных людей (образцов), например модели -- Species, Assembly, Chromosome, Coordinate, Allele
Ожидаемый результат
Проект на Джанго (версия 5.1, python версия 3.11), код которого доступен на https://github.com/. Зависимости этого проекта для conda/mamba указаны в файле env.yml, который находится в корне репозитория и будет использован для создания виртуального окружения (название окружения test-task-django). После клонирования репозитория достаточно выполнить следующие команды, чтобы запустилось рабочее решение, которое можно протестировать в браузере:

# создание виртуального окружения с помощью conda (или venv)
mamba env create -f dev.yml
mamba activate test-task-django

# Скачивание vcf файла
wget https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/latest/GRCh38/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz

# Создание тестовой базы данных
python manage migrate
python manage load_vcf HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz

# Запуск сервера django
python manage runserver

# API Запрос через браузер
http://127.0.0.1/api/get_genotypes/?chromosome=chr1&coordinate=1234
