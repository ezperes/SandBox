"""Dream Company Ecosystem: Bases: Spawn Manager"""


class SpawnManager:
    """Manages the spawn limits of its container class.

        PURPOSE
            To control, regarding class scope, the quantity of spawned agents.
            It is a class property object, defined in class scope.

        MECHANISM
            Every time an agent is up to be spawned, the spawner must check if
            spawn is allowed.
            Every time an agent is just spawned, the spawner must command
            increment of count
    """

    def __init__(self, max_spawn=float('inf')):
        self._max_spawn = max_spawn  # Maximum allowed number of spawned agents.
        self._count = 0  # Current count of spawned agents.

    @property
    def max_spawn(self):
        return self._max_spawn

    @max_spawn.setter
    def max_spawn(self, value=None, *args, **kwargs):
        raise AttributeError("Maximum allowed spawned agens is defined it agent definition code, "
                             "and can *NOT* be changed furthermore.")

    @property
    def count(self):
        return self._count

    def can_spawn(self) -> bool:
        """Checks whether a new spawning is allowed."""
        return self._count < self._max_spawn

    def inc_count(self):
        self._count += 1

    def reset_count(self):
        self._count = 0
