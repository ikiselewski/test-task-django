from django.urls import path

from .views import get_genotypes

urlpatterns = [
    path('get_genotypes/', get_genotypes, name='get_genotypes'),
]
