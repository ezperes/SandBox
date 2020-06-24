#import os
#os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Sandbox.settings')

from core.models import Exchange
from core.populate_data import *
from model_bakery import baker
from pprint import pprint
from names import get_full_name

# print("FINISHED.")
#a = baker.make(Genoma, _quantity=100)

#cpprint(a)


def test_populate():
    populate(Exchange, EXCHANGES, Exchange.name, 'Exchanges')
    # (Exchange, EXCHANGES, 'Exchanges')


test_populate()
