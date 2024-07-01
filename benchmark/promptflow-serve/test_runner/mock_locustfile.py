from locust import HttpUser, TaskSet, between, task


class UserBehavior(TaskSet):
    @task
    def test_endpoint(self):
        response = self.client.get("/")
        print(response.status_code, response.elapsed.total_seconds())


class WebsiteUser(HttpUser):
    tasks = [UserBehavior]
    wait_time = between(1, 2)
