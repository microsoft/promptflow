from locust import HttpUser, task


class TracingUser(HttpUser):
    @task
    def heartbeat(self):
        self.client.get("/heartbeat")
