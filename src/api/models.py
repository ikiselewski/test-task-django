from django.db import models


class Genotype(models.Model):
    chromosome = models.CharField(max_length=10, db_index=True)
    coordinate = models.IntegerField(db_index=True)
    ref = models.CharField(max_length=50)
    alt = models.CharField(max_length=50)
    gt = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['chromosome', 'coordinate']),
        ]
        verbose_name = 'Genotype'
        verbose_name_plural = 'Genotypes'

    def __str__(self):
        return f'Genotype {self.coordinate} chr{self.chromosome}'
