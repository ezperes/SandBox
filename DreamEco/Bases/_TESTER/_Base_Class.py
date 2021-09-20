from simple_classproperty import classproperty, ClasspropertyMeta

from DreamEco.Bases.BaseClass import DreamBaseClass


class Class1(DreamBaseClass):

    class Meta(DreamBaseClass.Meta):
        __max_spawn__ = 1



obj1 = Class1()

print("Maximum Allowed spawn: ", Class1.Meta.max_spawn)

# print("\nTrying to change __max_spawn__:")
# obj1.Meta.__max_spawn__ = 1
# print("__max_spawn__ now is: ", obj1.Meta.max_spawn)

try:
    print("\nTrying to change max_spawn property:")
    obj1.Meta.max_spawn = 1
    print("max_spawn now is: ", obj1.Meta.max_spawn)
except AttributeError as err:
    print("Property change is not allowed: ", err)

print("\nChecking Class1.Meta.max_spawn:", end=" ")
print(Class1.Meta.max_spawn)


obj2 = Class1()
print("\nobj2 max_spawn: ", obj2.Meta.max_spawn)

print("\nTrying to change obj2 max_spawn property:")
obj2.Meta.max_spawn = 200
print("New max spawn: ", obj2.Meta.max_spawn)
