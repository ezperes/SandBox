"""
    Command line django-admin.
    Purges selected databases
    source: https://docs.djangoproject.com/en/3.0/howto/custom-management-commands/
"""

from django.core.management.base import BaseCommand, CommandError
from core.populate_data import purge_main, purge_db, purge_all


class Command(BaseCommand):
    help = """Purges chosen sqlite3 databases from settings:
                    <no options>: purge main database.
                    all: purge all databases
           """
    def add_arguments(self, parser):
        parser.add_argument('databases', nargs='*', default=[])

    def handle(self, *args, **options):
        print('Purging required databases...')
        if not options['databases']:
            print("No database required: purging main database.")
            purge_main()
        else:
            print("Database required: %s" % options['databases'])

            # Pre-proccesses options
            options = [raw_option.strip().lower() for raw_option in options['databases']]

            # Processess options
            if 'all' in options:
                print("Purging all databases.")
                purge_all()
            else:
                purge_db(options)
