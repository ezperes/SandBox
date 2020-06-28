import os

from django.conf import settings


def get_all_db() -> list:
    """ Returns the name (str) of each settings' database in a list """
    all_dbs = [db_name for db_name in settings.DATABASES.keys()]
    return all_dbs


def get_db_path(database: str) -> 'path':
    db_settings = settings.DATABASES[database]
    return db_settings['NAME']


def purge_db(database: "db name or list of them"):
    """Deletes a list of sqlite3 db given as their string names"""
    if isinstance(database, str):
        database = list(database)
    if isinstance(database, list):
        all_db = get_all_db()
        for db in database:
            print("Purging %s" % db, end=': ... ')
            if db in all_db:
                try:
                    os.remove(get_db_path(db))
                    print("%s successfully purged." % db)
                except OSError as err:
                    print("%s: no such file or directory. No action with it." % err.filename)
                except IsADirectoryError as err:
                    print("The name '%s' is a directory. No action with it." % err.filename)
                except Exception as err:
                    print("Something wrong when deleting database file: %s" % err)
            else:
                print("%s is not in the settings database dictionary." % db)
    else:
        raise ValueError("purge_db() must receive the name (as string) or a list of names"
                         " of databases.")


def purge_main():
    purge_db('default')


def purge_all():
    purge_db(get_all_db())

