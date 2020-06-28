from json import dump

from EXCHANGES import EXCHANGES
from BROKERS import BROKERS
from ASSETS import ASSETS
from ASSET_TYPES import ASSET_TYPES


relative_path = './%s.json'

ENTITIES = [
    ('EXCHANGES', EXCHANGES),
    ('BROKERS', BROKERS),
    ('ASSETS', ASSETS),
    ('ASSET_TYPES', ASSET_TYPES)
]


def py_to_json():
    """Converts our .py data to .json"""

    for entity in ENTITIES:
        with open(relative_path % entity[0].upper(), 'w') as destination:
            dump(entity[1], destination)

py_to_json()
