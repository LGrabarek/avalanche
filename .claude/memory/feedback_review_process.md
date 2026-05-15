# Review process and expert panel

**Type:** feedback / process rule

After each implementation step is complete, follow this review pipeline. **Never skip a stage.**

1. **Self-test rigorously** — verify all functionality works before involving anyone else. Write invariant checks where you can (e.g. geometry bboxes, enum coverage). Run desktop smoke tests when the browser loop makes iteration slow.
2. **Expert panel review** — launch the 4 specialized agent reviewers in parallel (see `project_expert_panel.md`). Apply their findings. Re-run the panel on anything non-trivial.
3. **User review** — provide concrete, actionable instructions: what was accomplished, what works, how to test it, what to look for in the browser, success criteria, known quirks. Wait for explicit user approval before proceeding to the next step.

**Why:** The user stays in control of progress, catches issues early, and ensures each step is solid before the next builds on it. The user can also invoke the panel at any time by saying **"let the panel of experts review."**

**How to apply:**
- Never proceed to the next implementation step without completing all three review stages.
- User-review instructions must be concrete and actionable — not vague summaries. The `docs/STEP1_REVIEW.md` document is the template: how to run it, what to see, success checklist, resolved panel findings, known quirks, what to tell Claude afterward.
- Record approvals in `docs/PROGRESS.md` as they happen.
