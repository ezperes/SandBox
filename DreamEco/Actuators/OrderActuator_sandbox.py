""" Sandbox of prototype OrderActuator,
    for purpose of building TradeSensor Class """

from random import randint, choice
from core.MySymbol_sandbox import SYMBOLS
import pandas as pd


class OrdersActuator:
    """ Prototype for Order Class,
    for purpose of building
    the prototype of OrderActuator """

    def __init__(self, order_id, symbol):
        print("Creating object of class: %s | Id: %d" % (self.__class__, order_id))
        self._order_id = order_id
        self._filled = False
        self._symbol = symbol

    def verbose(self):
        """ Useless static method for testing purpose"""
        print("Order's ID: %d" % self._order_id)

    @staticmethod
    def get_random_number():
        """ Useless static method for testing purpose"""
        return randint(1000)

    def get_id(self):
        return self._order_id

    def get_symbol(self):
        return self._symbol

    def is_filled(self):
        return self._filled

    def set_filled(self):
        self._filled = True


class C0003_OrderActuator:
    """ Prototype for OrderActuator Class,
    for purpose of building
    the prototype of TradeSensor """



    pass

# Creates
df = pd.DataFrame(columns=['Orders'])


