from django.contrib import admin

from .models import Genotype


@admin.register(Genotype)
class GenotypeAdmin(admin.ModelAdmin):
    list_display = ('chromosome', 'coordinate', 'ref', 'alt', 'gt')
    list_filter = ('chromosome',)
    search_fields = ('chromosome', 'coordinate')
