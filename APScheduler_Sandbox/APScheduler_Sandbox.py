"""
Sandbox to learn to handle APScheduler
"""

import os, time
from datetime import datetime


def job1(*message):
    job1.counter += 1
    true_msg = " ".join(message) if type(message) == tuple or type(message) == list else message
    # if type(message) == tuple:
    #     true_msg = " ".join(message)
    print("Job 1 | Count: %d | Message: %s |Time: %s." % (job1.counter, true_msg, datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
job1.counter = 0


def job2():
    job2.counter += 1
    print("Job 2 | Count: %d | Time: %s." % (job1.counter, datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
job2.counter = 0

"""Recurrently prints a message n times within a fixed interval"""


from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

job = scheduler.add_job(job1, 'interval', seconds=10)

print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))

job1()

scheduler.start()

time.sleep(3.0)

job2()

scheduler.add_job(job2, 'interval', seconds=5)

try:
    # This is here to simulate application activity (which keeps the main thread alive).
    while True:
        time.sleep(5)
except (KeyboardInterrupt, SystemExit):
    # Not strictly necessary if daemonic mode is enabled but should be done if possible
    scheduler.shutdown()
