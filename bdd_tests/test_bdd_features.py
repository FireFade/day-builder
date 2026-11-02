from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when

DATE = "2026-11-03"

scenarios("features")


@given("the Day Builder API is running with a clean database")
def clean_api_state(client, bdd_state):
    bdd_state.clear()


@when(parsers.parse('I create an activity "{title}" lasting {duration:d} minutes'))
def create_activity(client, bdd_state, title, duration):
    bdd_state["response"] = client.post(
        "/api/activities",
        json={
            "title": title,
            "description": "Created by a BDD scenario",
            "category": "study",
            "duration_minutes": duration,
            "priority": 3,
            "required": True,
            "earliest_start": "08:00",
            "latest_end": "17:00",
            "recurrence": "daily",
            "target_date": None,
            "enabled": True,
        },
    )


@when('I submit an activity that does not fit its time window')
def submit_activity_outside_window(client, bdd_state):
    bdd_state["response"] = client.post(
        "/api/activities",
        json={
            "title": "Impossible activity",
            "category": "study",
            "duration_minutes": 60,
            "priority": 3,
            "required": True,
            "earliest_start": "10:00",
            "latest_end": "10:30",
            "recurrence": "daily",
            "enabled": True,
        },
    )


@then(parsers.parse("the API responds with status {status:d}"))
def response_has_status(bdd_state, status):
    assert bdd_state["response"].status_code == status, bdd_state["response"].text


@then(parsers.parse('the activity "{title}" is saved'))
def activity_is_saved(client, title):
    assert any(item["title"] == title for item in client.get("/api/activities").json())


@then("no activity was saved")
def no_activity_was_saved(client):
    assert client.get("/api/activities").json() == []


@when(parsers.parse('I create a schedulable activity named "{title}"'))
def create_scheduled_activity(client, bdd_state, title):
    bdd_state["response"] = client.post(
        "/api/activities",
        json={
            "title": title,
            "category": "study",
            "duration_minutes": 60,
            "priority": 4,
            "required": True,
            "earliest_start": "08:00",
            "latest_end": "17:00",
            "recurrence": "once",
            "target_date": DATE,
            "enabled": True,
        },
    )
    assert bdd_state["response"].status_code == 201, bdd_state["response"].text


@when("I preview the plan for the planning date")
def preview_plan(client, bdd_state):
    bdd_state["preview"] = client.post("/api/plans/preview", json={"on_date": DATE})
    assert bdd_state["preview"].status_code == 200, bdd_state["preview"].text


@then(parsers.parse('the preview contains activity "{title}"'))
def preview_has_activity(bdd_state, title):
    blocks = bdd_state["preview"].json()["blocks"]
    assert any(block["title"] == title and block["kind"] == "activity" for block in blocks)


@when("I confirm the previewed plan")
def confirm_preview(client, bdd_state):
    proposal = bdd_state["preview"].json()
    bdd_state["apply_response"] = client.post(
        "/api/plans/apply",
        json={"on_date": DATE, "revision": proposal["revision"]},
    )


@then("the plan is saved with the previewed activity")
def saved_plan_has_activity(client, bdd_state):
    assert bdd_state["apply_response"].status_code == 200, bdd_state["apply_response"].text
    saved = client.get(f"/api/plans/{DATE}").json()
    assert any(block["title"] == "Focus study" for block in saved["blocks"])


@when(parsers.parse('I add another activity named "{title}"'))
def add_another_activity(client, bdd_state, title):
    bdd_state["second_activity"] = client.post(
        "/api/activities",
        json={
            "title": title,
            "category": "personal",
            "duration_minutes": 30,
            "priority": 2,
            "required": True,
            "earliest_start": "08:00",
            "latest_end": "17:00",
            "recurrence": "once",
            "target_date": DATE,
            "enabled": True,
        },
    )
    assert bdd_state["second_activity"].status_code == 201


@when("I try to confirm the old preview")
def confirm_stale_preview(client, bdd_state):
    proposal = bdd_state["preview"].json()
    bdd_state["apply_response"] = client.post(
        "/api/plans/apply",
        json={"on_date": DATE, "revision": proposal["revision"]},
    )


@then("the API rejects the stale preview and no plan is saved")
def stale_preview_rejected(client, bdd_state):
    assert bdd_state["apply_response"].status_code == 409
    assert client.get(f"/api/plans/{DATE}").json() is None


@when(parsers.parse('I capture an inbox task "{title}"'))
def capture_inbox_task(client, bdd_state, title):
    bdd_state["inbox_response"] = client.post(
        "/api/inbox",
        json={"title": title, "notes": "Captured by a BDD scenario", "duration_minutes": 45, "priority": 4},
    )
    assert bdd_state["inbox_response"].status_code == 201, bdd_state["inbox_response"].text
    bdd_state["inbox_task"] = bdd_state["inbox_response"].json()


@then(parsers.parse('the inbox contains task "{title}" in the "{state}" state'))
def inbox_contains_task(client, title, state):
    items = client.get("/api/inbox").json()
    assert any(item["title"] == title and item["state"] == state for item in items)


@when("I schedule that inbox task for the planning date")
def schedule_inbox_task(client, bdd_state):
    task_id = bdd_state["inbox_task"]["id"]
    bdd_state["schedule_response"] = client.post(
        f"/api/inbox/{task_id}/schedule",
        json={"on_date": DATE, "category": "study", "required": True},
    )


@then("the inbox task becomes a scheduled activity")
def inbox_task_promoted(client, bdd_state):
    response = bdd_state["schedule_response"]
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "done"
    assert body["activity_id"] is not None
    bdd_state["scheduled_title"] = body["title"]


@then("the planning preview contains the scheduled inbox activity")
def preview_contains_inbox_activity(client, bdd_state):
    preview = client.post("/api/plans/preview", json={"on_date": DATE}).json()
    assert any(
        block["title"] == bdd_state["scheduled_title"] and block["kind"] == "activity"
        for block in preview["blocks"]
    )


@when("I try to schedule that inbox task again")
def schedule_inbox_task_twice(client, bdd_state):
    task_id = bdd_state["inbox_task"]["id"]
    bdd_state["duplicate_schedule"] = client.post(
        f"/api/inbox/{task_id}/schedule",
        json={"on_date": DATE, "category": "study", "required": True},
    )


@then("the duplicate scheduling request is rejected")
def duplicate_schedule_rejected(bdd_state):
    assert bdd_state["duplicate_schedule"].status_code == 409
