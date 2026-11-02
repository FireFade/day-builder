# language: en
Feature: Inbox task capture and scheduling
  Users can capture tasks first and promote them into a dated activity later.

  Background:
    Given the Day Builder API is running with a clean database

  Scenario: Capture a task in the inbox
    When I capture an inbox task "Read chapter"
    Then the inbox contains task "Read chapter" in the "inbox" state

  Scenario: Schedule an inbox task once
    When I capture an inbox task "Prepare lab"
    And I schedule that inbox task for the planning date
    Then the inbox task becomes a scheduled activity
    And the planning preview contains the scheduled inbox activity
    When I try to schedule that inbox task again
    Then the duplicate scheduling request is rejected
