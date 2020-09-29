from binance.client import Client


ezperes_keys = {
    'MyReadAnyIP': {
        'key': 'KJbcDGpTYzW2rLyTKdNqpUa4d96xxkwmUkQWB1Dm93iqaBtBVSyLCw3Qz2m5K9yQ',
        'secret_key': '1ZvvoGcNWvgSUHC2b6iOZNDFxeXa1fnOdVlsVDT3ORiRD8gK87ST7Dh8MmaOmZfk',
    },
}

my_key = ezperes_keys['MyReadAnyIP']['key']
my_sec_key = ezperes_keys['MyReadAnyIP']['secret_key']

client = Client(my_key, my_sec_key)

# 1. Get all Assets of Exchange
exchange_info = client.get_exchange_info()
symbols = exchange_info['symbols']






