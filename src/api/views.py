from django.http import JsonResponse

from .models import Genotype


def get_genotypes(request):
    chromosome = request.GET.get('chromosome')
    coordinate = request.GET.get('coordinate')

    genotypes = Genotype.objects.all()

    if chromosome:
        genotypes = genotypes.filter(chromosome=chromosome)
    if coordinate:
        try:
            coord = int(coordinate)
            genotypes = genotypes.filter(coordinate=coord)
        except ValueError:
            pass  # invalid coord

    data = [{
        'chromosome': g.chromosome,
        'coordinate': g.coordinate,
        'ref': g.ref,
        'alt': g.alt,
        'gt': g.gt,
    } for g in genotypes]

    return JsonResponse({'genotypes': data})
