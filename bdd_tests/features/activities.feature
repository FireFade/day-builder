# language: en
Feature: Activity catalog
  Users need valid activities to be available to the day planner.

  Background:
    Given the Day Builder API is running with a clean database

  Scenario: Create an activity that fits its time window
    When I create an activity "Study session" lasting 60 minutes
    Then the API responds with status 201
    And the activity "Study session" is saved

  Scenario: Reject an activity that does not fit its time window
    When I submit an activity that does not fit its time window
    Then the API responds with status 422
    And no activity was saved
