"""Dream Company Ecosystem: Agents: Verbosity Handler.


"""

from simple_classproperty import classproperty, ClasspropertyMeta


# Global dictionary which stablishes max and min values for verbosity level range
_verbose_level_range = {
    'min': 0,
    'max': 3,
}


class VerbosityHandler(metaclass=ClasspropertyMeta):

    # Whole runtime default verbosity level
    _runtime_verbosity_level = 0

    class Meta:
        # Class current version
        __version__ = '0.1.0'
        # Maximum allowed number of concurrent spawned agents
        __max_spawn__ = float('inf')

    @staticmethod
    def _check_level(val):
        """Checks whether *val* is in level range."""
        return type(val) == int and \
               _verbose_level_range['min'] <= val <= _verbose_level_range['max']

    @property
    def verbosity_level_range_min(self):
        return _verbose_level_range['min']

    @property
    def verbosity_level_range_max(self):
        return _verbose_level_range['max']

    @classproperty
    def runtime_verbosity_level(cls):
        return cls._runtime_verbosity_level

    @runtime_verbosity_level.setter
    def runtime_verbosity_level(cls, value):
        if cls._check_level(value):
            cls._runtime_verbosity_level = value
        else:
            raise ValueError("runtime_verbose_level must be an integer, "
                             "between %d and %d." % (_verbose_level_range['min'],
                                                     _verbose_level_range['max']))

    @property
    def verbosity_level(self):
        return self._verbosity_level

    @verbosity_level.setter
    def verbosity_level(self, value):
        if VerbosityHandler._check_level(value):
            self._verbosity_level = value
        else:
            raise ValueError("verbose_level must be an integer, "
                             "between %d and %d." % (_verbose_level_range['min'],
                                                     _verbose_level_range['max']))

    def __init__(self, verbosity_level=None, runtime_verbosity_level=None):

        if runtime_verbosity_level is not None:
            self.runtime_verbosity_level = runtime_verbosity_level

        if verbosity_level is not None:
            self.verbosity_level = verbosity_level
        else:
            self.verbosity_level = self.runtime_verbosity_level

    def verbose(self, message, message_verbose_level=None):

        level = message_verbose_level
        message_level = level if type(level) == int and level >= 0\
            else self.verbosity_level

        if message_level <= self.verbosity_level:
            print(message)
