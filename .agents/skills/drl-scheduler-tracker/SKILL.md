---
name: drl-scheduler-tracker
description: >-
  Custom project management skill for the AoI DRL Scheduler project.
  Guides the agent on how to track, manage, and update the task.md file,
  respect the owner decisions, and check dependencies between project phases.
---

# AoI DRL Scheduler Tracker Skill

You are working on the DRL-Based Age-of-Information-Aware Cross-Layer Scheduler project. This project is meticulously planned across 13 phases (P0-P12).

## Responsibilities

1. **Maintain `task.md`**: The `task.md` file in the root of the project is the single source of truth for project progress. Always keep it updated as you execute or complete work.
2. **Respect the Decision Matrix**: Section 21 of the blueprint established 15 critical owner decisions. These are listed at the top of `task.md`. **NO CODING TASKS MAY BE MOVED TO '🔵 IN PROGRESS' UNTIL ALL 15 DECISIONS ARE MARKED '✅ DONE' (Approved by Owner).**
3. **Task Statuses**: Use the exact statuses: `⬜ TODO`, `🔵 IN PROGRESS`, `✅ DONE`, `🔴 BLOCKED`, `⚠️ DECISION REQUIRED`.
4. **Phase Dependencies**: 
   - P1 (Hardware timing) MUST be completed before P2 (Simulation) can be fully parameterized.
   - P3 (Baselines) MUST be completed and pre-registered before P5 (DQN Training) generates results.
   - P8 (Firmware) can be run in parallel with P4-P7.
5. **Acceptance Criteria**: Before marking any task or phase as `✅ DONE`, you must ensure all Acceptance Criteria listed in `task.md` for that phase are met.
6. **Cross-Referencing**: Refer back to the `AoI_DRL_Scheduler_Engineering_Blueprint.md` whenever you need deep context or implementation details for a specific phase or task.
7. **Team Handoffs**: Since multiple team members are working on this via GitHub, always use the `partial_work.md` file to track the exact state of tasks that are currently `🔵 IN PROGRESS`.

## How to use this skill

When the user asks you to start work, check the status, or proceed to the next phase:
1. Read the current `task.md` to establish what is currently `🔵 IN PROGRESS` or what the next `⬜ TODO` is.
2. If a task is `🔵 IN PROGRESS`, **read `partial_work.md` immediately** to understand what was already done and where you or a team member left off.
3. Ensure no dependencies are violated (e.g., trying to start P2 before P1 parameters are known).
4. If coding is requested but decisions in the Owner Decision Matrix are still `⚠️ DECISION REQUIRED`, stop and prompt the user to resolve the decisions first.
5. When pausing work on a task that isn't fully completed, **you must write a handoff entry in `partial_work.md`** detailing what is done, what is broken, and what needs to happen next.
6. When a task is completed, use the `replace_file_content` tool to update its row in `task.md` to `✅ DONE`, and remove its entry from `partial_work.md`.
