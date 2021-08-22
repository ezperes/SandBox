"""Dream Company Ecosystem: Bases: BaseClass.

Bears Dream Company Base Classes.

The current Base Class is:
    - DreamBaseClass.
"""

from DreamEco.Handlers.Verbosity import VerbosityHandler


class DreamBaseClass:
    """ Dream Company Ecosystem Base Class.

    Generic Base Class to be Inherited by most of other Dream Company Base Classes
    and Real Clases.
    """

    class Meta:
        # Class current version
        __version__ = None
        # Maximum allowed number of concurrent spawned agents
        __max_spawn__ = float('inf')

    def __init__(self,
                 # VerbosityHandler init parameters
                 verbosity_level=None, runtime_verbosity_level=None):
        # Inits VerbosityHandler attribute
        self._verbosity = VerbosityHandler(
            verbosity_level, runtime_verbosity_level)
        # Creates alias for verbose method
        self.verbose = self._verbosity.verbose


baseobj = DreamBaseClass()
