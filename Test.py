from json import dump, load
from pprint import pprint
#
# # 1. Origin of data
# from core.populate_data import ASSET_TYPES
#
#
# # 2. Destination data file
# with open('core/populate_data/ASSET_TYPES.json', 'w') as destination:
#     dump(ASSET_TYPES, destination)

# 3. Tests the recorded file
with open('core/populate_data/ASSETS.json', 'r') as test_file:
    output = load(test_file)

    pprint(output)

from core.populate_data import ASSETS

def retrieve_name(var):
    return f'{var=}'.split('=')[0]


print(retrieve_name(ASSETS))
