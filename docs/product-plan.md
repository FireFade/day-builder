# Product analysis, MVP scope and development plan

## Core problem

Users often have fixed meetings plus personal routines (sleep, meals, exercise, study and leisure). A useful planner must solve scarce time, not merely visualize another to-do list.

## Competitor landscape (checked October 2026)

| Service | Verified current public feature | Differentiation opportunity |
|---|---|---|
| Motion | Auto-schedules and replans tasks as calendar changes | Local-first no mandatory paid LLM/API; explicit infeasibility |
| Reclaim.ai | Time protection for flexible routines/habits around calendar | Whole-life routines including meals and wake/sleep as first-class constraints |
| Sunsama | Guided daily planning, calendar integration and workload awareness | More automated schedule generation and hard constraints |
| Akiflow | Task/calendar integration, time-blocking and recurring tasks | Automated conflict-aware schedule, not primarily manual timeboxes |

Sources: https://www.usemotion.com/features/ai-calendar ; https://help.reclaim.ai/en/articles/17124978-habit-agent-overview-automate-recurring-routines ; https://help.sunsama.com/docs/integrations/calendar/ ; https://product.akiflow.com/en/help/articles/0006630-task-features

## Target user groups (hypotheses, not verified market data)

1. Knowledge workers with many work calls and fragmented availability.
2. Students juggling lectures, studying, meals, sleep, and part-time work.
3. Freelancers juggling multiple client calendars and deep work.
4. People who prioritize personal routines and sustainable daily scheduling.

Validation required: 15–25 user interviews, usability studies, churn/retention and willingness-to-pay experiments. Do not confuse qualitative hypotheses with measured market size.

## Main strengths and risks

**Strengths:** clear daily outcome, explainable constraints, personal and professional time together, usable free planning core.

**Risks:** complicated OAuth verification, employer tenant policies, synchronization consistency, false sense of optimality, high user input friction, reminders on iOS/PWA, privacy of work calendar titles, time zone edge cases.

**Important missing product features:** onboarding templates; time estimates from history; conflict explanation + manual override; calendar sync visibility and last-updated status; quiet hours and notification fatigue controls; travel/setup buffers; plan rollback/versioning; accessibility/keyboard navigation; offline-first cache with eventual sync; import/export of plans; transparent privacy dashboard.

## MVP split

**Slice 0.1 (implemented):** activities, manual fixed events, daily preferences/meals, schedule, plan persistence, marking done, rerun, warnings, offline web UI.

**MVP 0.2–0.3 (next):** Google read-only integration and robust synchronization, then Microsoft Graph integration (Outlook/Teams meetings) with OAuth.

**MVP 0.4:** quality improvements: OR-Tools search, partial tasks, missed deadline explanations, buffer and stable replan, recurring events expanded correctly.

**MVP 0.5:** notifications (service worker + server worker + monitoring), full auth/privacy for early external beta users.

**Post-MVP:** optional AI explanations, statistics/habits, mobile wrappers, optional paid tiers.

## User stories and acceptance criteria

### US1: Create activity

As a user, I want to add a named activity with duration, time window, priority and required flag.

- Given valid title and duration, when I save, then it persists and is displayed after page refresh.
- Given duration outside allowed range / invalid window, when I save, then API returns HTTP 422 and no invalid row is written.

### US2: Fixed meeting

As a user, I want a manual calendar event to be treated as immovable.

- Given an event at 10:00–11:00, when I build the plan, then planned meals/tasks are not placed over that time.
- Given two overlapping fixed events, when I build the plan, both are shown and an explicit warning is provided.

### US3: Plan generation

As a user, I want the planner to respect my sleep, meals, tasks and windows.

- Given compatible windows, when I generate the day, then it produces non-overlapping scheduled tasks and meals.
- Given impossible requirements, when I generate the day, then the engine returns warnings and leaves items unscheduled rather than creating impossible overlaps.
- Given saved plan, when I reload date, then the plan is returned from database.

### US4: Completion/replan

As a user, I want finished work preserved during recalculation.

- Given a completed task in today's plan, when I regenerate, then the completed block remains done and is not scheduled a second time.
- Given an additional meeting overlapping completed work, when recalculated, then the previous completed work is preserved with a warning.

## Implementation sequence

1. **Completed:** initial product requirements, architecture, schema, API, deterministic planner, local web UI and API automated tests.
2. **Next:** auth strategy and multi-user model; integration test harness with calendar adapters and test-only OAuth credentials.
3. **Then:** Google OAuth flow, sync cursors, exception/calendar recurrence handling, permissions and encrypted secrets.
4. **Then:** Microsoft Graph OAuth and sync; multi-account de-duplication.
5. **Then:** advanced optimization, execution feedback, overdue/missed task flows.
6. **Then:** notification delivery server / Web Push / optional Telegram, consent and platform behavior validation.
7. **Finally:** production deployment and monitoring, security review, user testing, monetization experiments.

## Planner library choice

- **Greedy algorithm:** low dependency overhead, fast; can miss feasible complete solutions.
- **Bounded backtracking/MRV (current):** good constraints coverage on small personal-day problem; bounded search may miss feasibility and is not necessarily globally optimal.
- **OR-Tools CP-SAT (planned):** suitable for hard/soft constraints and rigorous objective priorities, at the cost of extra solver dependency, modeling effort and performance tuning.

Recommendation: ship a trusted local slice first, then move to CP-SAT before claiming optimality or SaaS readiness.

## External technical references

Google Calendar auth/scopes: https://developers.google.com/workspace/calendar/api/auth

Google Calendar incremental sync: https://developers.google.com/workspace/calendar/api/guides/sync

Microsoft Graph calendar view: https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0

Microsoft Graph delta: https://learn.microsoft.com/en-us/graph/delta-query-events

Apple Web Push limitations: https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers
