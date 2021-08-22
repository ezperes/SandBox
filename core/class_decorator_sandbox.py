"""Class tests sandbox"""
from simple_classproperty import classproperty, ClasspropertyMeta

from DreamEco.Handlers.Verbosity import VerbosityHandler


class parentclass1:

    _static_var_class1 = 0

    def __init__(self, argparent1):
        print(f"Parentclass1: {argparent1}")

    def meth1(self, msg1="My msg"):
        print("meth1", msg1)


class parentclass2:

    def __init__(self, argparent1):
        print(f"Parentclass1: {argparent1}")


class newclass(parentclass1, parentclass2,
               VerbosityHandler, metaclass=ClasspropertyMeta):

    def __init__(self, runtime_verbosity_level=0):
        self.tmeth = self.meth1
        VerbosityHandler.__init__(self, runtime_verbosity_level)

    @classproperty
    def class_attr(cls):
        return cls._static_var_class1

    @class_attr.setter
    def class_attr(cls, value):
        if isinstance(value, (int, float)):
            cls._static_var_class1 = value
        else:
            raise ValueError('class_attr must be set with a valid number')


myobj = newclass()

myobj.tmeth('obj call')
