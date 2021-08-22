"""
    ft0006SENSORS >> ft00061TIME SENSOR module component
        Handles time sensitive events within DREAM ECOSYSTEM
        by using the classes below
"""
from apscheduler.schedulers.background import BackgroundScheduler


class TimerSensor:
    """ Manages scheduled jobs within DREAM ECOSYSTEM """

    def __init__(self):
        self.background_scheduler = BackgroundScheduler()
        self.background_scheduler.start()

    def __del__(self):
        self.background_scheduler.remove_all_jobs()
        try:
            self.background_scheduler.shutdown()
        except:
            print("Scheduler not running.")

    def add_recurrent_job(self, function, args=(), kwargs={}, id="", immediate=True, **trigger_args) -> "job":
        """Adds a recurrent job with default settings"""
        if immediate:
            function(*args, **kwargs)
        return self.background_scheduler.add_job(function, 'interval', args=args, kwargs=kwargs, id=id, **trigger_args)
