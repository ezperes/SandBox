from django.db.models import Model, Field


def populate(model: Model, itens: tuple, uniqueness: Field = None, label: str = None) -> None:
    """Populates a model with a given set of dictionary data
            uniqueness determinates the uniqueness field criterion
            label is for console prompt info only
    """
    print('Populating %s' % (label if label else ' '))

    if not uniqueness:
        for nr, item in enumerate(itens):
            created_item, created = model.objects.get_or_create(**item)
            print('%03d. "%s" %s in database.' % (nr, created_item, 'created' if created else 'already exists'))
    else:
        for nr, item in enumerate(itens):
            created_item, created = model.objects.get_or_create(uniqueness=item.pop(uniqueness))
            for field in item:
                created_item[field] = item.pop(field)
            created_item.save()
            print('%03d. "%s" %s in database.' % (nr, created_item, 'created' if created else 'already exists'))
