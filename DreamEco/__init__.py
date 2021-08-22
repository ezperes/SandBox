"""
M00000_RTEnvironment
Functionality 00000: Runtime Environemnt

Runtime Environment (RTEnv) is a centralized logic space where the existance and operations of all agents
take place.

The RTEnv is composed by HANDLERS, SENSORS and ACTUATORS

    HANDLERS
    Handlersare centralized mechanisms to deal with specific duties within operating in the environment.
    e.g.: AgentsHandler, which is responsible to spawn, set triggers, unset triggers, and despawn agents.

    SENSORS
    Sensors are centralized doorways to fetch/receive information from outer world.
    Sensors optimize and centralize the gathering of information from sources other than DreamEco
    (i.e. the outer world regarding the Ecosystem).

    Sensors are to provide SENTIENCE to the DreamEco.
    Considering that DreamEco is a sort of engine that process data into information, and such data are born in
    the world outside the Ecosystem, sensors act as a doorway so data gathering is optimized and kept under control.

    Sensors provide control, security, reliability, bandwidth and storage optimization, within the activity of data
    acquisition for the processing subsystems of  DreamEco.

    Receive requests from DreamEco components and respond them. Manage events from outer world, as timer, network, etc.


"""

# Imports
from .main import RunTimeEnvironment
# from M0000_RTEnvironment.M00000_AgentsHandler import AgentsHandler
# from M0000_RTEnvironment.M00001_TimerSensor import TimerSensor

# Module Metadata
__version__ = '0.1.0'


# Main Environment Class
# class Environment:
#
#     def __init__(self):
#
#         # The Environment's Agent Handler
#         self.agents = AgentsHandler()
#
#         # The Environment's Timer Sensor
#         self.timer = TimerSensor()
#
#
# class C1:
#
#     def __init__(self, my_id):
#         self.my_id = my_id
#
#     def meth(self):
#         print("This is class %s, and it's id is %d" % (self.__class__, self.my_id))
#
#
# class C2(C1):
#     pass
#
#
# class C3(C2):
#     pass
#
#
# class TEST_Environment(Environment):
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.multispawn()
#         self.print_agents()
#
#     def multispawn(self):
#         for i in range(20):
#             classes = [C1, C2, C3]
#             chosen_class = choice(classes)
#             self.agents.spawn(chosen_class, i)
#
#     def print_agents(self):
#         for agent in self.agents.agents.values():
#             agent.meth()
#
#
# tester = TEST_Environment()
