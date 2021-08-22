class C1:

    def __init__(self, a):
        print("c1 init")
        self.a = a

    def m1(self):
        print("c1 m1")


class C2:

    def __init__(self, a, b):
        print("c2 init")
        self.a = a
        self.b = b

    def m1(self):
        print("c2 m1")

    def m2(self):
        print("c2 m2")


class C3(C1, C2):

    def __init__(self, a1, a2, b, c):
        print("c3 init")
        C1.__init__(self, a1)
        C2.__init__(self, a2, b)
        self.c = c


c3 = C3("a1", "a2", "b", "c")
