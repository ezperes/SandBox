"""
    Command line django-admin. Populates database with pre-chosen exchanges data
    source: https://docs.djangoproject.com/en/3.0/howto/custom-management-commands/
"""

from django.core.management.base import BaseCommand, CommandError
from core.models import Exchange
from core.populate_data.EXCHANGES import EXCHANGES


class Command(BaseCommand):
    help = 'Populates database with pre-chosen Exchanges data'

    def handle(self, *args, **options):
        print('Populating Exchanges')
        for curr_exchange in EXCHANGES:
            exchange, created = Exchange.objects.get_or_create(name=curr_exchange['name'])
            if created:
                self.stdout.write('"%s" created in database.' % curr_exchange['name'])
            else:
                self.stdout.write('"%s" exists in database.' % curr_exchange['name'])
