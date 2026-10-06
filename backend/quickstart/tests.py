# Some tests created with aid from Gemini
from typing import Any

import pytest
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient

from .models import StudyUser, Task

# TODO Add docstrings to each of these functions to help newcomers understand what they do


@pytest.fixture
def api_client() -> APIClient:
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def test_user(db: Any) -> StudyUser:
    """Creates a StudyUser for testing"""
    return StudyUser.objects.create_user(username="andres", password="password123", money=500)


@pytest.fixture
def other_user(db: Any) -> StudyUser:
    """Creates another StudyUser for isolation testing"""
    return StudyUser.objects.create_user(username="anthony", password="password456", money=50)


@pytest.fixture
def test_task(db: Any, test_user: StudyUser) -> Task:
    """Creates a Task for testing"""
    return Task.objects.create(
        name="Test",
        reward=50,
        description="Make sure this works",
        due_date="2026-12-31",
        user=test_user,
    )


@pytest.mark.tasks
class TestTaskCreation:
    def test_create_task_authenticated(self, api_client: APIClient, test_user: StudyUser) -> None:
        api_client.force_authenticate(user=test_user)

        # 2. Prepare Data (No user info in JSON, handled by CurrentUserDefault)
        url = "/api/create_task/"
        # TODO Make a TaskData class that strongly types the fields inside our StudyUser
        data = {
            "name": "Math Homework",
            "reward": 50,
            "description": "Finish algebra 1",
            "due_date": "2029-12-31",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        # Verify DB entry
        task: Task = Task.objects.get(name="Math Homework")
        assert task.user == test_user

    def test_create_task_unauthenticated(self, api_client: APIClient) -> None:
        """Ensure logged-out users can't create tasks."""
        url = "/api/create_task/"
        data = {
            "name": "Ghost Task",
            "due_date": "2029-12-31",
        }

        response = api_client.post(url, data, format="json")

        assert isinstance(response, Response)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_task_missing_due_date(
        self,
        api_client: APIClient,
        test_user: StudyUser,
    ) -> None:
        api_client.force_authenticate(user=test_user)
        data = {
            "name": "No Date Task",
            "reward": 50,
            "description": "test",
        }

        response = api_client.post("/api/create_task/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_task_invalid_due_date(
        self,
        api_client: APIClient,
        test_user: StudyUser,
    ) -> None:
        """Malformed date should be rejected."""
        api_client.force_authenticate(user=test_user)
        data = {
            "name": "Bad Date Task",
            "reward": 50,
            "due_date": "not-a-date",
        }

        response = api_client.post("/api/create_task/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_task_negative_reward(self, api_client: APIClient, test_user: StudyUser) -> None:
        api_client.force_authenticate(user=test_user)
        data = {
            "name": "Negative Task",
            "reward": -100,
            "due_date": "2029-12-31",
        }

        response = api_client.post("/api/create_task/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_task_positive_reward(self, api_client: APIClient, test_user: StudyUser) -> None:
        api_client.force_authenticate(user=test_user)
        data = {
            "name": "Positive Task",
            "reward": 100,
            "due_date": "2029-12-31",
        }

        response = api_client.post("/api/create_task/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_task_due_date_in_past(
        self, api_client: APIClient, test_user: StudyUser
    ) -> None:
        api_client.force_authenticate(user=test_user)
        data = {
            "name": "Late Task",
            "reward": 10,
            "due_date": "2000-01-01",
        }

        response = api_client.post("/api/create_task/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.tasks
@pytest.mark.parametrize("test_username", ["andres"])
class TestTaskRetrieval:
    def test_get_task_authenticated(
        self,
        api_client: APIClient,
        test_user: StudyUser,
        test_task: Task,
        test_username: str,
    ) -> None:
        # Log in
        user = StudyUser.objects.get(username=test_username)
        api_client.force_authenticate(user=user)

        # Make the request
        url = "/api/get_task/"
        query_params = {"username": test_username}
        response = api_client.get(url, data=query_params)

        assert response.status_code == status.HTTP_200_OK

        assert response.data[0]["name"] == "Test"

    def test_get_task_unauthenticated(self, api_client: APIClient, test_username: str) -> None:
        url = "/api/get_task/"
        query_params = {"username": test_username}
        response = api_client.get(url, data=query_params)

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.tasks
class TestTaskIsolation:
    def test_task_belongs_to_requesting_user(
        self,
        api_client: APIClient,
        test_user: StudyUser,
    ) -> None:
        """Task should be assigned to the authenticated user, not someone else."""
        api_client.force_authenticate(user=test_user)
        data = {"name": "My Task", "reward": 50}
        api_client.post("/api/create_task/", data, format="json")

        assert Task.objects.filter(name="My Task", user=test_user).exists()

    def test_users_cannot_see_each_others_tasks(
        self,
        api_client: APIClient,
        test_user: StudyUser,
        other_user: StudyUser,
    ) -> None:
        """Tasks created by one user shouldn't appear for another."""
        api_client.force_authenticate(user=test_user)
        api_client.post("/api/create_task/", {"name": "Private Task", "reward": 10}, format="json")

        api_client.force_authenticate(user=other_user)
        response = api_client.get("/api/get_task/")
        task_names = [task["name"] for task in response.data]
        assert "Private Task" not in task_names

    def test_isolation_holds_across_multiple_tasks_per_user(
        self,
        api_client: APIClient,
        test_user: StudyUser,
        other_user: StudyUser,
    ) -> None:
        api_client.force_authenticate(user=test_user)
        for i in range(3):
            api_client.post(
                "/api/create_task/",
                {"name": f"Mine {i}", "reward": 5, "due_date": "2029-12-31T00:00:00Z"},
                format="json",
            )

        api_client.force_authenticate(user=other_user)
        for i in range(2):
            api_client.post(
                "/api/create_task/",
                {"name": f"Theirs {i}", "reward": 5, "due_date": "2029-12-31T00:00:00Z"},
                format="json",
            )

        response = api_client.get("/api/get_task/")
        names = [t["name"] for t in response.data]

        assert len(names) == 2
        assert all(name.startswith("Theirs") for name in names)

    def test_same_task_name_allowed_across_different_users(
        self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
    ) -> None:
        """Task names aren't globally unique — two users can each have a task with the same name."""
        Task.objects.create(
            name="Homework", reward=10, due_date="2029-12-31T00:00:00Z", user=test_user
        )
        Task.objects.create(
            name="Homework", reward=20, due_date="2029-12-31T00:00:00Z", user=other_user
        )

        assert Task.objects.filter(name="Homework").count() == 2
        mine = Task.objects.get(name="Homework", user=test_user)
        theirs = Task.objects.get(name="Homework", user=other_user)
        assert mine.id != theirs.id
        assert mine.reward != theirs.reward

    def test_user_cannot_access_task_by_guessing_id(
        self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
    ) -> None:
        """Sequential/guessable IDs shouldn't let one user fetch another's specific task."""
        task = Task.objects.create(
            name="Secret Task", reward=10, due_date="2029-12-31T00:00:00Z", user=other_user
        )

        api_client.force_authenticate(user=test_user)
        response = api_client.get("/api/get_task/", data={"id": task.id})

        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)

    def test_isolation_holds_after_switching_authenticated_user_mid_session(
        self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
    ) -> None:
        """Re-authenticating as a different user on the same client shouldn't leak the previous user's tasks."""
        api_client.force_authenticate(user=test_user)
        api_client.post(
            "/api/create_task/",
            {"name": "First User Task", "reward": 5, "due_date": "2029-12-31T00:00:00Z"},
            format="json",
        )

        api_client.force_authenticate(user=other_user)
        response = api_client.get("/api/get_task/")

        names = [t["name"] for t in response.data]
        assert "First User Task" not in names

    def test_create_task_does_not_expose_other_users_task_count(
        self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
    ) -> None:
        """Creating a task for one user shouldn't be influenced by or leak another user's existing tasks."""
        Task.objects.create(
            name="Existing", reward=10, due_date="2029-12-31T00:00:00Z", user=other_user
        )

        api_client.force_authenticate(user=test_user)
        response = api_client.post(
            "/api/create_task/",
            {"name": "New Task", "reward": 5, "due_date": "2029-12-31T00:00:00Z"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Task.objects.filter(user=test_user).count() == 1
        assert Task.objects.filter(user=other_user).count() == 1

    def test_get_task_count_matches_only_authenticated_users_tasks(
        self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
    ) -> None:
        """Total tasks in the DB across all users shouldn't affect what one user sees."""
        Task.objects.create(
            name="Mine 1", reward=5, due_date="2029-12-31T00:00:00Z", user=test_user
        )
        Task.objects.create(
            name="Theirs 1", reward=5, due_date="2029-12-31T00:00:00Z", user=other_user
        )
        Task.objects.create(
            name="Theirs 2", reward=5, due_date="2029-12-31T00:00:00Z", user=other_user
        )
        Task.objects.create(
            name="Theirs 3", reward=5, due_date="2029-12-31T00:00:00Z", user=other_user
        )

        api_client.force_authenticate(user=test_user)
        response = api_client.get("/api/get_task/")

        assert response.status_code == status.HTTP_200_OK
        assert Task.objects.count() == 4  # confirms all 4 exist in the DB
        assert len(response.data) == 1  # but only 1 is visible to test_user

    def test_creating_many_tasks_for_one_user_does_not_appear_for_another(
        self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
    ) -> None:
        """Bulk creation for one user should never leak into another user's view."""
        api_client.force_authenticate(user=test_user)
        for i in range(10):
            api_client.post(
                "/api/create_task/",
                {"name": f"Task {i}", "reward": 1, "due_date": "2029-12-31T00:00:00Z"},
                format="json",
            )

        api_client.force_authenticate(user=other_user)
        response = api_client.get("/api/get_task/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_task_reward_values_are_isolated_between_users(
        self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
    ) -> None:
        """Confirm reward/money fields on tasks aren't cross-contaminated between users' tasks."""
        Task.objects.create(name="Cheap", reward=1, due_date="2029-12-31T00:00:00Z", user=test_user)
        Task.objects.create(
            name="Expensive", reward=1000, due_date="2029-12-31T00:00:00Z", user=other_user
        )

        api_client.force_authenticate(user=test_user)
        response = api_client.get("/api/get_task/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["reward"] == 1

    def test_get_task_only_returns_own_tasks(
        self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
    ) -> None:
        """Create tasks interleaved between two users, confirm isolation without relying on IDs."""
        api_client.force_authenticate(user=test_user)
        api_client.post(
            "/api/create_task/",
            {"name": "A", "reward": 1, "due_date": "2029-12-31T00:00:00Z"},
            format="json",
        )

        api_client.force_authenticate(user=other_user)
        api_client.post(
            "/api/create_task/",
            {"name": "B", "reward": 1, "due_date": "2029-12-31T00:00:00Z"},
            format="json",
        )

        api_client.force_authenticate(user=test_user)
        response = api_client.get("/api/get_task/")
        names = [t["name"] for t in response.data]

        assert "A" in names
        assert "B" not in names

@pytest.mark.required
@pytest.mark.tasks
class TestTaskDeletion:
    def test_delete_task_authenticated_owner(
        self, api_client: APIClient, test_user: StudyUser, test_task: Task
    ) -> None:
        """The owner of a task should be able to delete it."""
        api_client.force_authenticate(user=test_user)

        response = api_client.delete(f"/api/delete_task/{test_task.id}/")

        assert response.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT)
        assert not Task.objects.filter(id=test_task.id).exists()

    def test_delete_task_unauthenticated(self, api_client: APIClient, test_task: Task) -> None:
        """A logged-out request should not be able to delete anything."""
        response = api_client.delete(f"/api/delete_task/{test_task.id}/")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Task.objects.filter(id=test_task.id).exists()

    def test_delete_task_nonexistent_id(self, api_client: APIClient, test_user: StudyUser) -> None:
        """Deleting an ID that doesn't exist should 404, not 500."""
        api_client.force_authenticate(user=test_user)

        response = api_client.delete("/api/delete_task/999999/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_task_other_users_task_forbidden(
        self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
    ) -> None:
        """A user should not be able to delete a task they don't own."""
        task = Task.objects.create(
            name="Not Yours", reward=10, due_date="2029-12-31T00:00:00Z", user=other_user
        )

        api_client.force_authenticate(user=test_user)
        response = api_client.delete(f"/api/delete_task/{task.id}/")

        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
        assert Task.objects.filter(id=task.id).exists()

    def test_delete_task_removes_only_target_task(
        self, api_client: APIClient, test_user: StudyUser
    ) -> None:
        """Deleting one task shouldn't affect the user's other tasks."""
        task1 = Task.objects.create(
            name="Keep", reward=5, due_date="2029-12-31T00:00:00Z", user=test_user
        )
        task2 = Task.objects.create(
            name="Remove", reward=5, due_date="2029-12-31T00:00:00Z", user=test_user
        )

        api_client.force_authenticate(user=test_user)
        response = api_client.delete(f"/api/delete_task/{task2.id}/")

        assert response.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT)
        assert Task.objects.filter(id=task1.id).exists()
        assert not Task.objects.filter(id=task2.id).exists()

    def test_delete_task_invalid_id_format(
        self, api_client: APIClient, test_user: StudyUser
    ) -> None:
        """A non-numeric ID in the URL shouldn't cause a 500."""
        api_client.force_authenticate(user=test_user)

        response = api_client.delete("/api/delete_task/not-an-id/")

        assert response.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST)

    def test_delete_task_twice_second_call_fails_gracefully(
        self, api_client: APIClient, test_user: StudyUser, test_task: Task
    ) -> None:
        """Deleting the same task twice shouldn't 500 on the second attempt."""
        api_client.force_authenticate(user=test_user)

        first = api_client.delete(f"/api/delete_task/{test_task.id}/")
        second = api_client.delete(f"/api/delete_task/{test_task.id}/")

        assert first.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT)
        assert second.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_task_response_has_no_body_or_confirms_deletion(
        self, api_client: APIClient, test_user: StudyUser, test_task: Task
    ) -> None:
        """If the view returns 200 with a body, confirm it doesn't leak the deleted object's user info."""
        api_client.force_authenticate(user=test_user)

        response = api_client.delete(f"/api/delete_task/{test_task.id}/")

        if response.status_code == status.HTTP_200_OK and response.data:
            assert "password" not in response.data
            assert "user" not in response.data or not isinstance(response.data.get("user"), dict)

    def test_delete_task_get_request_not_allowed(
        self, api_client: APIClient, test_user: StudyUser, test_task: Task
    ) -> None:
        """A GET to the delete endpoint shouldn't accidentally delete anything."""
        api_client.force_authenticate(user=test_user)

        response = api_client.get(f"/api/delete_task/{test_task.id}/")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert Task.objects.filter(id=test_task.id).exists()

    def test_delete_task_does_not_affect_other_users_tasks(
        self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
    ) -> None:
        """Deleting your own task shouldn't touch anyone else's."""
        my_task = Task.objects.create(
            name="Mine", reward=5, due_date="2029-12-31T00:00:00Z", user=test_user
        )
        their_task = Task.objects.create(
            name="Theirs", reward=5, due_date="2029-12-31T00:00:00Z", user=other_user
        )

        api_client.force_authenticate(user=test_user)
        api_client.delete(f"/api/delete_task/{my_task.id}/")

        assert Task.objects.filter(id=their_task.id).exists()

    def test_delete_task_does_not_delete_user(
        self, api_client: APIClient, test_user: StudyUser, test_task: Task
    ) -> None:
        """Deleting a task should never cascade upward and delete the owning user."""
        api_client.force_authenticate(user=test_user)

        api_client.delete(f"/api/delete_task/{test_task.id}/")

        assert StudyUser.objects.filter(id=test_user.id).exists()

    def test_delete_task_negative_id(self, api_client: APIClient, test_user: StudyUser) -> None:
        """A negative ID should be handled gracefully, not cause a 500."""
        api_client.force_authenticate(user=test_user)

        response = api_client.delete("/api/delete_task/-1/")

        assert response.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST)

    def test_delete_task_inactive_user_cannot_delete(
        self, api_client: APIClient, test_user: StudyUser, test_task: Task
    ) -> None:
        """A deactivated account shouldn't be able to delete tasks either."""
        test_user.is_active = False
        test_user.save()

        api_client.force_authenticate(user=test_user)
        response = api_client.delete(f"/api/delete_task/{test_task.id}/")

        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        assert Task.objects.filter(id=test_task.id).exists()

    def test_delete_task_reduces_users_task_count(
        self, api_client: APIClient, test_user: StudyUser
    ) -> None:
        """Confirm the count of the user's remaining tasks drops by exactly one."""
        Task.objects.create(name="A", reward=1, due_date="2029-12-31T00:00:00Z", user=test_user)
        task_b = Task.objects.create(
            name="B", reward=1, due_date="2029-12-31T00:00:00Z", user=test_user
        )
        Task.objects.create(name="C", reward=1, due_date="2029-12-31T00:00:00Z", user=test_user)

        api_client.force_authenticate(user=test_user)
        api_client.delete(f"/api/delete_task/{task_b.id}/")

        assert Task.objects.filter(user=test_user).count() == 2

    def test_delete_task_does_not_return_stale_data_on_get_after_delete(
        self, api_client: APIClient, test_user: StudyUser, test_task: Task
    ) -> None:
        """After deleting a task, a subsequent get_task call shouldn't still show it."""
        api_client.force_authenticate(user=test_user)

        api_client.delete(f"/api/delete_task/{test_task.id}/")
        response = api_client.get("/api/get_task/")

        assert response.status_code == status.HTTP_200_OK
        names = [t["name"] for t in response.data]
        assert test_task.name not in names

    def test_delete_task_id_belonging_to_different_task_type_or_missing_fk(
        self, api_client: APIClient, test_user: StudyUser
    ) -> None:
        """Deleting a task whose id was already reassigned/reused after a prior deletion shouldn't 500."""
        task = Task.objects.create(
            name="Temp", reward=5, due_date="2029-12-31T00:00:00Z", user=test_user
        )
        deleted_id = task.id
        task.delete()

        api_client.force_authenticate(user=test_user)
        response = api_client.delete(f"/api/delete_task/{deleted_id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND


# Test Graveyard for tests that get generated but aren't useful *yet*

# def test_deleting_user_cascades_to_tasks(
#     self, api_client: APIClient, test_user: StudyUser
# ) -> None:
#     Task.objects.create(
#         name="Cascade Task",
#         reward=10,
#         due_date="2029-12-31T00:00:00Z",
#         user=test_user,
#     )
#     test_user.delete()

#     assert not Task.objects.filter(name="Cascade Task").exists()

# Isolation Tests! (might need to make a second class)

# def test_user_cannot_delete_another_users_task(
#         self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
#     ) -> None:
#         """A user should not be able to delete a task they don't own."""
#         task = Task.objects.create(
#             name="Other's Task", reward=10, due_date="2029-12-31", user=other_user
#         )

#         api_client.force_authenticate(user=test_user)
#         response = api_client.delete(f"/api/delete_task/{task.id}/")

#         assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
#         assert Task.objects.filter(id=task.id).exists()

# def test_user_cannot_update_another_users_task(
#     self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
# ) -> None:
#     """A user should not be able to modify a task they don't own."""
#     task = Task.objects.create(
#         name="Original Name", reward=10, due_date="2029-12-31", user=other_user
#     )

#     api_client.force_authenticate(user=test_user)
#     response = api_client.patch(
#         f"/api/update_task/{task.id}/", {"name": "Hacked Name"}, format="json"
#     )

#     assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
#     task.refresh_from_db()
#     assert task.name == "Original Name"

# def test_deleting_one_user_does_not_affect_other_users_tasks(
#     self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
# ) -> None:
#     """Cascade delete should only remove the deleted user's own tasks."""
#     Task.objects.create(name="Mine", reward=10, due_date="2029-12-31", user=test_user)
#     Task.objects.create(name="Theirs", reward=10, due_date="2029-12-31", user=other_user)

#     test_user.delete()

#     assert not Task.objects.filter(name="Mine").exists()
#     assert Task.objects.filter(name="Theirs").exists()

# def test_same_task_name_allowed_across_different_users(
#     self, api_client: APIClient, test_user: StudyUser, other_user: StudyUser
# ) -> None:
#     """Task names aren't globally unique — two users can each have a task with the same name."""
#     Task.objects.create(name="Homework", reward=10, due_date="2029-12-31", user=test_user)
#     Task.objects.create(name="Homework", reward=20, due_date="2029-12-31", user=other_user)

#     assert Task.objects.filter(name="Homework").count() == 2
#     mine = Task.objects.get(name="Homework", user=test_user)
#     theirs = Task.objects.get(name="Homework", user=other_user)
#     assert mine.id != theirs.id
#     assert mine.reward != theirs.reward
