from django.db import models

class Genoma(models.Model):

    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField()

    def __str__(self):
        return "%s | %s | %s" % (self.id, self.name, self.order)
