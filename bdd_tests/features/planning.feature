# language: en
Feature: Preview and confirm a day plan
  A plan is only saved after the user confirms the current preview.

  Background:
    Given the Day Builder API is running with a clean database

  Scenario: Confirm a current preview
    When I create a schedulable activity named "Focus study"
    And I preview the plan for the planning date
    Then the preview contains activity "Focus study"
    When I confirm the previewed plan
    Then the plan is saved with the previewed activity

  Scenario: Reject a preview after its inputs have changed
    When I create a schedulable activity named "Focus study"
    And I preview the plan for the planning date
    And I add another activity named "Walk"
    When I try to confirm the old preview
    Then the API rejects the stale preview and no plan is saved
