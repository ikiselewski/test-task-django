from django.urls import path

from .views import GenotypeListView

urlpatterns = [
    path(
        'get_genotypes/',
        GenotypeListView.as_view(),
        name='get_genotypes',
    ),
]
