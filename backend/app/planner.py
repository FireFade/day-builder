"""Offline, deterministic, constraint-aware scheduler (15-minute granularity).

No ML API required.  Its backtracking search is deliberately bounded: this first
vertical slice is a local MVP, not an optimal CP-SAT scheduling implementation.
"""
from dataclasses import dataclass
from datetime import date
from .schemas import minutes

STEP = 15
SEARCH_LIMIT = 16000

@dataclass(frozen=True)
class Job:
    key: str
    title: str
    kind: str
    category: str
    source_id: int | None
    length: int
    earliest: int
    latest: int
    preferred: int
    priority: int
    explanation: str
    before: int = 0
    after: int = 0
    depends_on: tuple[str, ...] = ()


def conflict(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def ceil_step(number: int) -> int:
    return (number + STEP - 1) // STEP * STEP


def is_active(activity, on_date: date, policy=None) -> bool:
    if not activity.enabled:
        return False
    if policy:
        if policy.start_date and on_date < policy.start_date: return False
        if policy.end_date and on_date > policy.end_date: return False
        if policy.weekdays and on_date.weekday() not in policy.weekdays: return False
        anchor = policy.start_date or activity.target_date
        if anchor and policy.repeat_every_days > 1 and (on_date - anchor).days % policy.repeat_every_days: return False
    if activity.recurrence == "custom":
        return bool(policy and policy.start_date)
    if activity.recurrence == "once":
        return activity.target_date == on_date
    if activity.recurrence == "weekdays":
        return on_date.weekday() < 5
    if activity.recurrence == "weekends":
        return on_date.weekday() >= 5
    return True


def available_positions(job: Job, occupied: list[tuple[int, int]]) -> list[int]:
    results = []
    for start in range(ceil_step(job.earliest + job.before), job.latest - job.length - job.after + 1, STEP):
        if all(not conflict(start - job.before, start + job.length + job.after, a, b) for a, b in occupied):
            results.append(start)
    results.sort(key=lambda x: (abs(x - job.preferred), x))
    return results


def solve(jobs: list[Job], occupied: list[tuple[int, int]]) -> dict[str, int] | None:
    """MRV backtracking, returns feasible assignment or None; never fakes success."""
    if not jobs:
        return {}
    steps = 0

    def recurse(remaining: list[Job], taken: list[tuple[int, int]], placed: dict[str, int]) -> dict[str, int] | None:
        nonlocal steps
        steps += 1
        if steps > SEARCH_LIMIT:
            return None
        if not remaining:
            return placed
        candidate_list = [(available_positions(job, taken), job) for job in remaining]
        candidate_list.sort(key=lambda pair: (len(pair[0]), -pair[1].priority, pair[1].key))
        options, selected = candidate_list[0]
        if not options:
            return None
        rest = [job for job in remaining if job.key != selected.key]
        for start in options:
            next_placed = {**placed, selected.key: start}
            def valid_order():
                for job in jobs:
                    if job.key not in next_placed: continue
                    for dep in job.depends_on:
                        if dep in next_placed:
                            ancestor = next(j for j in jobs if j.key == dep)
                            if next_placed[dep] + ancestor.length > next_placed[job.key]: return False
                return True
            if not valid_order(): continue
            result = recurse(rest, [*taken, (start-selected.before, start+selected.length+selected.after)], next_placed)
            if result is not None: return result
        return None

    return recurse(jobs, occupied, {})


def generate(on_date: date, prefs, activities, events, completed=None, preserved=None, skipped=None, policies=None) -> tuple[list[dict], list[str]]:
    """Produces feasible blocks, warnings about unscheduled items and fixed conflicts."""
    wake = minutes(prefs.wake_time)
    sleep = minutes(prefs.sleep_time)
    warnings: list[str] = []
    blocks: list[dict] = []
    occupied: list[tuple[int, int]] = []
    done_activity_ids = set(skipped or [])
    completed_ids = {b.source_id for b in (completed or []) if b.kind == 'activity'}
    preserved_meals = set()
    activity_by_id = {activity.id: activity for activity in activities}
    policies = policies or {}

    # Completed, manually locked, and user-created blocks survive regeneration.
    # If a newly arriving meeting overlaps one of them, surface a warning.
    for old in [*(completed or []), *(preserved or [])]:
        # A saved completed/locked block must not override a later change to
        # the source activity's recurrence or target date. Custom blocks are
        # intentionally independent of the underlying recurring activities.
        if old.kind == 'activity':
            source = activity_by_id.get(old.source_id)
            if source is None or not is_active(source, on_date, policies.get(source.id)):
                continue
        block = dict(
            kind=old.kind, source_id=old.source_id, title=old.title,
            category=old.category, start_min=old.start_min, end_min=old.end_min,
            status=old.status, is_locked=bool(getattr(old, "is_locked", False)),
            explanation=("Збережено виконану активність" if old.status == 'done' else
                         "Закріплений або власний блок: час збережено"),
        )
        blocks.append(block)
        occupied.append((old.start_min, old.end_min))
        if old.kind == "activity" and old.source_id is not None:
            done_activity_ids.add(old.source_id)
        if old.kind == "meal":
            preserved_meals.add(old.title)

    fixed = sorted(events, key=lambda e: (minutes(e.start_time), e.id))
    for event in fixed:
        start, end = minutes(event.start_time), minutes(event.end_time)
        if any(conflict(start, end, a, b) for a, b in occupied):
            warnings.append(f"Подія «{event.title}» перетинається з уже виконаною активністю")
        for previous in fixed:
            if previous.id == event.id:
                break
            if conflict(start, end, minutes(previous.start_time), minutes(previous.end_time)):
                warnings.append(f"Перетин календарних подій: «{previous.title}» та «{event.title}»")
        blocks.append(dict(
            kind="event", source_id=event.id, title=event.title, category="work",
            start_min=start, end_min=end, status="pending",
            explanation="Фіксована календарна подія: її час не змінюється",
        ))
        occupied.append((start, end))

    jobs: list[Job] = []
    for meal in prefs.meals:
        if meal["title"] in preserved_meals:
            continue
        earliest = max(wake, minutes(meal["earliest_start"]))
        latest = min(sleep, minutes(meal["latest_end"]))
        length = meal["duration_minutes"]
        jobs.append(Job(
            key=f'meal:{meal["key"]}', title=meal["title"], kind="meal", category="health",
            source_id=None, length=length, earliest=earliest, latest=latest,
            preferred=ceil_step((earliest + latest - length) // 2), priority=5,
            explanation="Прийом їжі в межах налаштованого часового вікна",
        ))

    for activity in activities:
        policy=policies.get(activity.id)
        if policy and policy.due_date and on_date>policy.due_date and activity.enabled:
            warnings.append(f"Прострочений дедлайн: «{activity.title}» — {policy.due_date}")
        if not is_active(activity, on_date, policy) or activity.id in done_activity_ids:
            continue
        earliest = max(wake, minutes(activity.earliest_start))
        latest = min(sleep, minutes(activity.latest_end))
        # Block time for preparation, travel and post-task rest without moving
        # the visible activity itself; never squeeze buffers over a meeting.
        before=(policy.prep_minutes+policy.travel_minutes) if policy else 0
        after=policy.break_after_minutes if policy else 0
        preferred=minutes(policy.preferred_start) if policy and policy.preferred_start else earliest
        if policy and policy.energy >= 4 and not policy.preferred_start:
            # Suggest demanding work in the user's explicit energy window.
            peak_start=minutes(getattr(prefs,'energy_peak_start','09:00'))
            peak_end=minutes(getattr(prefs,'energy_peak_end','12:00'))
            if peak_end-peak_start >= activity.duration_minutes + before + after:
                preferred=max(earliest, peak_start+before)
        dependencies=tuple(f'activity:{i}' for i in (policy.depends_on or [])) if policy else ()
        jobs.append(Job(
            key=f"activity:{activity.id}", title=activity.title, kind="activity",
            category=activity.category, source_id=activity.id, length=activity.duration_minutes,
            earliest=earliest, latest=latest, preferred=ceil_step(preferred),
            priority=activity.priority,
            explanation=("Обов'язкова активність" if activity.required else "Необов'язкова активність") +
                        (f" · дедлайн {policy.due_date}" if policy and policy.due_date else "") +
                        (f" · підготовка/дорога {before} хв" if before else "") +
                        (f" · перерва {after} хв" if after else ""),
            before=before,after=after,depends_on=dependencies,
        ))

    known_job_keys={j.key for j in jobs}
    invalid_dependents={j.key for j in jobs if any(dep not in known_job_keys and int(dep.partition(':')[2]) not in completed_ids for dep in j.depends_on)}
    for job in jobs:
        if job.key in invalid_dependents:
            warnings.append(f"Залежність активності «{job.title}» не запланована на цей день")
    jobs=[j for j in jobs if j.key not in invalid_dependents]
    required = [j for j in jobs if j.kind == "meal" or next((a.required for a in activities if a.id == j.source_id), False)]
    optional = [j for j in jobs if j not in required]
    # A required task cannot depend on an optional predecessor that is omitted.
    # Escalate such prerequisites to required for this day, transitively.
    changed=True
    while changed:
        changed=False
        demanded={dep for j in required for dep in j.depends_on}
        for previous in list(optional):
            if previous.key in demanded:
                optional.remove(previous);required.append(previous);changed=True

    assignment = solve(required, occupied)
    if assignment is None:
        # When the complete set is infeasible, retain the most important feasible subset.
        assignment = {}
        accepted: list[Job] = []
        order = sorted(required, key=lambda j: (j.kind != "meal", -j.priority,
            (policies.get(j.source_id).due_date-on_date).days if j.source_id in policies and policies[j.source_id].due_date else 9999,
            j.latest - j.earliest - j.length, j.key))
        for job in order:
            if any(dep not in {j.key for j in accepted} and int(dep.partition(':')[2]) not in completed_ids for dep in job.depends_on):
                warnings.append(f"Не вдалося запланувати «{job.title}»: спершу потрібно виконати залежне завдання")
                continue
            feasible = solve([*accepted, job], occupied)
            if feasible is None:
                warnings.append(f"Не вдалося запланувати обов'язкову активність «{job.title}» ({job.length} хв): бракує вільного часу або сумісного часового вікна")
            else:
                accepted.append(job)
                assignment = feasible

    missing_minutes = sum(job.length for job in required if job.key not in assignment)
    if missing_minutes:
        warnings.insert(0, f"Не вдалося запланувати {missing_minutes} хв обов'язкових справ або харчування через зайнятість чи часові обмеження")

    for job in required:
        if job.key in assignment:
            start = assignment[job.key]
            occupied.append((start-job.before, start + job.length+job.after))
            assignment[job.key] = start
            blocks.append(dict(
                kind=job.kind, source_id=job.source_id, title=job.title, category=job.category,
                start_min=start, end_min=start + job.length, status="pending", explanation=job.explanation,
            ))

    for job in sorted(optional, key=lambda j: (-j.priority,
        (policies.get(j.source_id).due_date-on_date).days if j.source_id in policies and policies[j.source_id].due_date else 9999,
        j.latest, j.key)):
        if any(dep not in assignment and int(dep.partition(':')[2]) not in completed_ids for dep in job.depends_on):
            warnings.append(f"Необов'язкова активність «{job.title}» чекає на попередню справу")
            continue
        positions = available_positions(job, occupied)
        # Enforce predecessors on optional jobs too.
        for dep in job.depends_on:
            if dep in assignment:
                ancestor=next((j for j in jobs if j.key==dep),None)
                if ancestor: positions=[s for s in positions if s>=assignment[dep]+ancestor.length]
        if positions:
            start = positions[0]
            occupied.append((start-job.before, start + job.length+job.after))
            assignment[job.key] = start
            blocks.append(dict(
                kind=job.kind, source_id=job.source_id, title=job.title, category=job.category,
                start_min=start, end_min=start + job.length, status="pending", explanation=job.explanation,
            ))
        else:
            warnings.append(f"Необов'язкова активність «{job.title}» не вмістилася в день")
    blocks.sort(key=lambda b: (b["start_min"], b["end_min"], b["title"]))
    return blocks, warnings
