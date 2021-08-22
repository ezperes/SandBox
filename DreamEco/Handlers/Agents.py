""" Handles the existance and operating of agents within RTEnv """


class AgentsHandler:

    def __init__(self):
        self.agents = dict()

    def spawn(self, agent_class, *args, **kwargs):
        """ Spawns a new agent within Agents Handler
            :params:
            :agent_class:
        """
        new_agent = agent_class(*args, **kwargs)
        self.agents[hash(new_agent)] = new_agent

    def despawn(self, my_id):
        del(self.agents[my_id])
