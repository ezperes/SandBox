"""
    Command line django-admin. Populates database with pre-chosen exchanges data
    source: https://docs.djangoproject.com/en/3.0/howto/custom-management-commands/
"""

from django.core.management.base import BaseCommand, CommandError
from core.populate_data.populates import populate_all, populate_exchanges, populate_brokers, \
    populate_assets

class Command(BaseCommand):
    help = 'Populates database with chosen data'

    def add_arguments(self, parser):
        parser.add_argument('entities', nargs='*', default=[])

    def handle(self, *args, **options):
        print('Populating required entities...')
        if not options['entities']:
            print("No entities required: Processing all entities.")
            populate_all()
        else:
            print("Entities required: %s" % options['entities'])
            for raw_option in options['entities']:
                option = raw_option.strip().lower()
                print("Raw option: %s" % raw_option)
                print("Proccessed option: %s" % option)
                print("Detected option(s):")
                if option == 'all':
                    print("Processing all entities.")
                    populate_all()
                else:
                    if option == 'asset' or option == 'assets':
                        print("\tProcessing Assets")
                        populate_assets()
                    elif option == 'broker' or option == 'brokers':
                        print("\tProcessing Brokers")
                        populate_brokers()
                    elif option == 'exchange' or option == 'exchanges':
                        print("\tProcessing Exchanges")
                        populate_exchanges()
