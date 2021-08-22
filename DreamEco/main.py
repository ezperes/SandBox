""" M0000_RTEnvironment module mastercode """

from DreamEco.Handlers.Agents import AgentsHandler
from DreamEco.Sensors.TimerSensor import TimerSensor


# Main Environment Class
class RunTimeEnvironment:
    """ Runtime Environment class

        Incapsulates the handlers, sensor and actuators of fully funtional
        Runtime Environment within Dream Company Ecosystem
    """
    def __init__(self):

        # The Environment's Handlers
        self.agents = AgentsHandler()

        # The Environment's Sensors
        self.timer = TimerSensor()
