from django.db import models
from core.populate_data import ASSET_TYPES, EXCHANGES


class Genoma(models.Model):

    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField()

    def __str__(self):
        return "%s | %s | %s" % (self.id, self.name, self.order)


class Exchange(models.Model):
    name = models.CharField(max_length=60)

    def __str__(self):
        return self.name

class Broker(models.Model):
    name = models.CharField(max_length=60)

    def __str__(self):
        return self.name


class Asset(models.Model):
    symbol = models.CharField(max_length=30)
    description = models.CharField(max_length=60)
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPES)
    root = models.BooleanField(default=True)
    root_asset = models.ForeignKey('self', null=True, on_delete=models.CASCADE, related_name='derived_assets')
    base_asset = models.ForeignKey('self', null=True, on_delete=models.PROTECT, related_name='underlying_asset')
    quote_asset = models.ForeignKey('self', null=True, on_delete=models.PROTECT, related_name='quoted_asset')

    def __str__(self):
        return self.symbol
