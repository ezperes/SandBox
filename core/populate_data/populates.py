from core.models import Exchange
from .EXCHANGES import EXCHANGES
from .populate import populate

def populate_exchanges() -> None:
    """Populates database with initial Exchanges"""
    populate(model=Exchange, itens=EXCHANGES, label='Exchange', uniqueness=Exchange.name)



