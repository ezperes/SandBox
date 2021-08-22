class sensor:

    def get(self):
        pass

    def set(self):
        pass

class job_timer(sensor):

    def __init__(self):
        self.jobs = dict()

    def get(self, job_id, job_info):
        return self.jobs[job_id].__getattribute__(job_info)

    def _get_job(self, job_id):
        return self.jobs[job_id]

my_job_controller = job_timer()

for i in range(1,11):
    my_job_controller.jobs[i] = "Job %d" % i

