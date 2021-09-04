""" Handles the existance and operating of agents within RTEnv """

from DreamEco.Bases.BaseClass import DreamBaseClass


class AgentsHandler(DreamBaseClass):

    def __init__(self):

        # Inits base classes
        DreamBaseClass.__init__(self)

        self._agents = dict()

    def spawn(self, agent_class, *args, **kwargs):
        """ Spawns a new agent within Agents Handler
            :params:
            :agent_class:
        """
        new_agent = agent_class(*args, **kwargs)
        self._agents[hash(new_agent)] = new_agent

    def despawn(self, my_id):
        del(self._agents[my_id])
