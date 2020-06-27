from core.models import Exchange, Broker, Asset
from .EXCHANGES import EXCHANGES
from .BROKERS import BROKERS
from .ASSETS import ASSETS
from .populate import populate


def populate_exchanges() -> None:
    """Populates database with initial Exchanges"""
    populate(model=Exchange, items=EXCHANGES, label='Exchange', uniqueness=Exchange.name)


def populate_brokers() -> None:
    """Populates database with initial Brokers"""
    populate(model=Broker, items=BROKERS, label='Brokers', uniqueness=Broker.name)


def populate_assets() -> None:
    """Populates database with initial Assets"""
    populate(model=Asset, items=ASSETS, label='Assets', uniqueness=Asset.name)


def populate_all() -> None:
    """Populates database with all initial data"""
    populate_assets()
    populate_brokers()
    populate_exchanges()
