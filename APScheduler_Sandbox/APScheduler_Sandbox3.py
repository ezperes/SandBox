import M000Environment.M00061_TimerSensor as timer
import time
from datetime import datetime


def job1(*message):
    job1.counter += 1
    true_msg = " ".join(message) if type(message) == tuple or type(message) == list else message
    print("Job 1 | Count: %d | Message: %s |Time: %s." % (job1.counter, true_msg,
                                                          datetime.now().strftime("%d/%m/%Y %H:%M:%S")))


job1.counter = 0


def job2():
    job2.counter += 1
    print("Job 2 | Count: %d | Time: %s." % (job2.counter, datetime.now().strftime("%d/%m/%Y %H:%M:%S")))


job2.counter = 0

mytimer = timer.C00061_TimerSensor()

job1_handler = mytimer.add_recurrent_job(job1, args=('Testing Message',), id='job1', seconds=3)

time.sleep(4)

job2_handler = mytimer.add_recurrent_job(job2, id='job2', seconds=3)

time.sleep(30)

