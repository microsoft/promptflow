from locust import HttpUser, TaskSet, between, task


class UserBehavior(TaskSet):
    @task
    def test_endpoint(self):
        response = self.client.post("/score", json={"question": "Test question", "chat_history": []})
        print(response.status_code, response.elapsed.total_seconds(), response.json())


class WebsiteUser(HttpUser):
    tasks = [UserBehavior]
    wait_time = between(1, 2)
