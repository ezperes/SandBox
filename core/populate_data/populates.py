""" Populates database with given data """

from core.models import Exchange, Broker, Asset
from json import load
from ._populate import populate

relative_path = 'core/populate_data/%s.json'


def load_json(entity: str) -> 'data':
    """Returns the content of <entity>.json file
        contained in <relative_path>
    """
    with open(relative_path % entity.upper(), 'r') as source_file:
        return load(source_file)


def populate_exchanges() -> None:
    """Populates database with initial Exchanges"""
    populate(model=Exchange, items=load_json('EXCHANGES'),
             label='Exchange', uniqueness=Exchange.name)


def populate_brokers() -> None:
    """Populates database with initial Brokers"""
    populate(model=Broker, items=load_json('BROKERS'),
             label='Brokers', uniqueness=Broker.name)


def populate_assets() -> None:
    """Populates database with initial Assets"""
    populate(model=Asset, items=load_json('ASSETS'),
             label='Assets', uniqueness=Asset.name)


def populate_all() -> None:
    """Populates database with all initial data"""
    populate_assets()
    populate_brokers()
    populate_exchanges()
