from random import choice

from .main import RunTimeEnvironment


class C1:

    def __init__(self, my_id):
        self.my_id = my_id

    def meth(self):
        print("This is class %s, and it's id is %d" % (self.__class__, self.my_id))


class C2(C1):
    pass


class C3(C2):
    pass


class TEST_Environment(RunTimeEnvironment):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.multispawn()
        self.print_agents()

    def multispawn(self):
        for i in range(20):
            classes = [C1, C2, C3]
            chosen_class = choice(classes)
            self.agents.spawn(chosen_class, i)

    def print_agents(self):
        for agent in self.agents._agents.values():
            agent.meth()


tester = TEST_Environment()
