from DreamEco.Bases._Spawn_Manager import SpawnManager
from DreamEco.Bases.BaseClass import DreamBaseClass


class C1(DreamBaseClass):

    class Meta:
        spawn_manager = SpawnManager(10)

    def __init__(self):

        DreamBaseClass.__init__(self, verbosity_level=3)

        self._manager = type(self).Meta.spawn_manager
        _max = self._manager.max_spawn
        _count = self._manager.count

        self.verbose("*"*80, 2)
        self.verbose(f"Current spawned amount is: {_count}", 2)
        self.verbose(f"Maximum allowed is: {_max}", 2)

        self.verbose("Can spawn?")
        if C1.Meta.spawn_manager.can_spawn():
            self._manager.inc_count()
            self.verbose(f"Count incremented {self._manager.count}\n" +
                         "="*60 + "\n\n", 2)
        else:
            raise RuntimeError(f"Can NOT spawn. Maximum number of agents "
                               f"({self._manager.max_spawn}) overflow.")

        self.verbose("Class C1 instantiated", 2)


obj1 = C1()
