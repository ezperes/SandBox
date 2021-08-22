#from django.test import TestCase

# Create your tests here.

from difflib import get_close_matches, SequenceMatcher
from pprint import pprint

test_group = ["My testing string",
              "another one bites the dust",
              "We are the champions",
              "WHO wants to live forever"
              ]


def normalize_str(mystr: str):
    return mystr.upper().split()


def normalized_str_list(str_list: list):
    return list(map(normalize_str, str_list))


def join_raw_str(strlist: list):
    return [inner for outter in normalized for inner in outter]

def make_test():
    normalized = normalized_str_list(test_group)
    raw_list = join_raw_str(normalized)

    mykeyword = input("Enter Key-word: ")
    mykeyword = mykeyword.upper()

    return any(mykeyword in s for s in raw_list)


def check_similarities():

    word_list = [
        'Lane',
        'Triceract',
        'Populous',
        'Range',
        'Range',
        'Geene',
        'Genious',
        'Rampant',
        'Canopus',
        'Lord',
        'overlord',
        'overlorf',
        'overhauled',
    ]
    searched = [
        'GEEEne',
        'Overlord',
        'triceratops',
        'rampage',
        'canon',
        'Ramp',
        'Ranger',
        'Layer',
        'population',
        'people',

    ]

    # Creates dictionary in format:
    #   { searched_word : { tested_word : rate } }
    result = {searched_word: {tested_word:
                              SequenceMatcher(None,
                                              searched_word.upper(),
                                              tested_word.upper()).ratio()
                              for tested_word in word_list
                              if SequenceMatcher(None,
                                                 searched_word.upper(),
                                                 tested_word.upper()
                                                 ).ratio() >= 0.49
                              }
              for searched_word in searched}

    word_list.sort()
    searched.sort()

    print("="*60)
    print("The search space:")
    pprint(word_list)

    print("="*60)
    print("The searched ones are:")
    pprint(searched)

    print("="*60)
    print("The result is: ")
    pprint(result)


check_similarities()

# mykw = input("Enter keyword: ")
# matches = get_close_matches(mykw, test_group)
