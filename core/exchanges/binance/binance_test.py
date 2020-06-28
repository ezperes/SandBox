"""
Binance testing script
    Tests to be done
    1. Connect to Binance perpetual testnet
    2. Get Exchange Info
        1. Store Symbols in a local SQLite3 DB

"""

from binance_f import RequestClient
from binance_f.base.printobject import PrintMix

from core.models import *

perpetual_testnet_eduardo = {
    'api_key': '96bMhGS6lGKvdPsC7d8KHkqj9KMHvlSKpNaagzqkMbZrN2a64KsQ0rlMycLLgtax',
    'secret_key': '4yCB7pDKRb82mpl44s8165US3MCNOuFwsSrbUEF0O4HQJJAWRRHWDy5fxun8UQR3',
    'url': 'https://testnet.binancefuture.com'
}

perpetual_eduardo = {
    'api_key': '96bMhGS6lGKvdPsC7d8KHkqj9KMHvlSKpNaagzqkMbZrN2a64KsQ0rlMycLLgtax',
    'secret_key': '4yCB7pDKRb82mpl44s8165US3MCNOuFwsSrbUEF0O4HQJJAWRRHWDy5fxun8UQR3',
    'url': 'https://testnet.binancefuture.com'
}


request_client = RequestClient(**perpetual_testnet_eduardo)
exchange_info = request_client.get_exchange_information()

print("======= Exchange Information =======")
print("timezone: ", exchange_info.timezone)
print("serverTime: ", exchange_info.serverTime)
print("=== Rate Limits ===")
PrintMix.print_data(exchange_info.rateLimits)
print("===================")
print("=== Exchange Filters ===")
PrintMix.print_data(exchange_info.exchangeFilters)
print("===================")
print("=== Symbols ===")
PrintMix.print_data(exchange_info.symbols)
print("===================")
print("====================================")

"""
def test(**kwargs):
    if kwargs['api_key']:
        print('API key: %s' % kwargs['api_key'])

test(**perpetual_testnet_eduardo)
"""
