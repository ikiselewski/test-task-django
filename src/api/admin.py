from django.contrib import admin

from .models import (
    Allele,
    Assembly,
    Chromosome,
    Coordinate,
    Genotype,
    GenotypeAltAllele,
    Sample,
    Species,
)


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    list_display = ('name', 'common_name')
    search_fields = ('name', 'common_name')


@admin.register(Assembly)
class AssemblyAdmin(admin.ModelAdmin):
    list_display = ('name', 'species', 'accession')
    list_filter = ('species',)
    search_fields = ('name', 'accession')
    autocomplete_fields = ('species',)


@admin.register(Chromosome)
class ChromosomeAdmin(admin.ModelAdmin):
    list_display = ('name', 'assembly', 'length')
    list_filter = ('assembly',)
    search_fields = ('name',)
    autocomplete_fields = ('assembly',)


@admin.register(Coordinate)
class CoordinateAdmin(admin.ModelAdmin):
    list_display = ('chromosome', 'position')
    list_filter = ('chromosome__assembly', 'chromosome')
    search_fields = ('chromosome__name',)
    autocomplete_fields = ('chromosome',)


@admin.register(Allele)
class AlleleAdmin(admin.ModelAdmin):
    list_display = ('sequence',)
    search_fields = ('sequence',)


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ('name', 'species', 'aliases')
    list_filter = ('species',)
    search_fields = ('name', 'aliases')
    autocomplete_fields = ('species',)


class GenotypeAltAlleleInline(admin.TabularInline):
    model = GenotypeAltAllele
    extra = 0
    autocomplete_fields = ('allele',)


@admin.register(Genotype)
class GenotypeAdmin(admin.ModelAdmin):
    list_display = (
        'sample',
        'chromosome_name',
        'position',
        'ref',
        'alt',
        'gt',
        'rsid',
    )
    list_filter = (
        'sample',
        'coordinate__chromosome__assembly',
        'coordinate__chromosome',
    )
    search_fields = (
        'sample__name',
        'coordinate__chromosome__name',
        'rsid',
        'gt',
    )
    autocomplete_fields = ('sample', 'coordinate', 'ref_allele')
    inlines = [GenotypeAltAlleleInline]
    list_select_related = (
        'sample',
        'coordinate',
        'coordinate__chromosome',
        'ref_allele',
    )

    @admin.display(description='chromosome', ordering='coordinate__chromosome__name')
    def chromosome_name(self, obj: Genotype) -> str:
        return obj.chromosome_name

    @admin.display(description='position', ordering='coordinate__position')
    def position(self, obj: Genotype) -> int:
        return obj.position

    @admin.display(description='ref')
    def ref(self, obj: Genotype) -> str:
        return obj.ref
