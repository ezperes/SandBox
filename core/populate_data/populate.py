from django.db.models import Model
from django.db.models.query_utils import DeferredAttribute
from pprint import pprint

def populate(model: Model, items: list, uniqueness=None, label: str = None) -> None:
    """Populates a model database with a given set of dictionary data
            uniqueness is a mandatory and is the uniqueness field criterion
                can contain field objects or field name strings,  or list of these
            label is for console prompt info only
    """

    def raise_err():
        raise ValueError("Uniqueness must be a django.db.models.query_utils.Deferred\
                            Attribute(field), a name of a field, or a list of such objects.")

    # 1. Initialization
    print("="*80)
    print('Populating model %s' % (label if label else ' '))

    # 2. Validates and transforms inputs

    # 2.1 If uniqueness exists, validates and tranforms it
    if uniqueness is not None or uniqueness:
        print("Validating inputs", end="... ")
        # 2.1.1 uniqueness must be a Field instante or list of Fields
        if isinstance(uniqueness, DeferredAttribute):
            print("Uniqueness is DeferredAttribute(field) instance")
            uniqueness = (uniqueness,)
        elif isinstance(uniqueness, (tuple, list)):
            print("Uniqueness is a list or tuple. Checking it's content...")
            for unique in uniqueness:
                if isinstance(unique, DeferredAttribute):
                    print(unique, " is a DeferredAttribute(field).")
                elif isinstance(unique, str):
                    print(unique, " is a string (hope it corresponds to a field name).")
                else:
                    raise_err()

        # 2.1.2 Transforms Uniqueness
        if isinstance(uniqueness, str):
            uniqueness_names = [uniqueness, ]
        else:
            uniqueness_names = list()
            for unique in uniqueness:
                uniqueness_names.append(unique.field.name)
        print("Inputs validated.")
    else:
        raise_err()

    # 3. Stores items' data
    print("Populating...")
    for i, entry in enumerate(items):
        print("-" * 50)
        print(" "*4, "Item : %02d" % (i+1))
        print(" "*4, "entry: ", entry)
        unique_fields = dict()
        ordinary_fields = dict()
        for field, value in entry.items():
            print(" "*8, "Field: %s \n" % field,
                  " "*12, "Value: %s" % (value))
            if field in uniqueness_names:
                unique_fields[field] = value
            else:
                ordinary_fields[field] = value
        print(" "*4, "Unique Fields:", unique_fields)
        print(" "*4, "Ordinary Fields:", ordinary_fields)
        created_record, created = model.objects.get_or_create(defaults=ordinary_fields, **unique_fields)
        print("\n", " "*3, 'VEREDICT: "%s" %s in database. \n' %
              (created_record, 'created' if created else 'already exists'))
