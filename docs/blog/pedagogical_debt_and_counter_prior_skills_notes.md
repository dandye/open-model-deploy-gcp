# Research notes, terminology, and citations

Working notes and verbatim quotes for *"Pedagogical debt: why web tutorials teach models to over-privilege your cloud, and how skills fix the prior"*.

## Alternative titles and hooks

- **Pedagogical debt: why web tutorials teach models to over-privilege your cloud**
- **The Hello-World prior: why coding agents default to tutorial shortcuts and how skills fix them**
- **Disclaimer laundering: how pre-training turns "for testing only" into your production IAM policy**
- **Knowledge injection vs. prior correction: the two jobs of agent skills**

## Reusable pull-quotes for papers and talks

> "Tutorials optimize for time-to-Hello-World, not least privilege. When we pre-train on the web, we convert humanity's pedagogical shortcuts into the model's default prior, stripped of the original 'do not use in production' disclaimer. Agent skills are not just for adding missing knowledge; they are counter-priors that override what a million quickstarts taught the model to do."

> "The baseline model did not fail because of a knowledge deficit. It knew `gcloud secrets add-iam-policy-binding` existed. It failed because in its training corpus, bloggers explaining Cloud Run in five minutes outnumber security engineers hardening production vaults by a hundred to one."

> "Counter-prior skills are probabilistic steering: shifting an agent from 20% compliance to 95% compliance wins a 72-trial benchmark. But when the pre-trained reflex is `git add .` and an untracked `.env` file is sitting on disk, a 5% slip rate still means rotating your API keys in public. Skills steer the prior; deterministic hooks enforce the invariant."

## Core terminology definitions

- **Pedagogical debt.** A security or architectural shortcut taken by a tutorial author to minimize extraneous cognitive load and reach "Hello World" faster (`gcloud projects add-iam-policy-binding`, `git add .`, `chmod 777`, `CORS: *`, `verify=False`).
- **The Hello-World prior (or Tutorial gravity).** The statistical bias of next-token predictors toward introductory quickstart patterns over production-hardened patterns, caused by the numerical dominance of beginner tutorials on the open web.
- **Disclaimer laundering.** The process by which pre-training ingests high-frequency insecure code blocks while disconnecting them from the surrounding prose warnings ("for local testing only; scope this down in production").
- **Counter-prior skill.** An inference-time agent skill whose primary purpose is not to introduce unseen APIs (knowledge injection), but to suppress a dominant pre-training antipattern so the model selects a safer low-frequency API it already knows.
- **Finish-line context decay.** The tendency of an agent at the end of a long debugging trajectory (when rules files in the initial system prompt are tens of thousands of tokens away) to revert to high-probability pre-trained macro sequences such as `git add . && git commit && git push`, overriding negative rules in `AGENTS.md`.
- **Commit-zero scaffolding skill (`skel`).** A skill that executes at step 0 (project initialization) to write deterministic guardrails (`.gitignore` with `.env` excluded from the start, `.env.example`, `AGENTS.md`) into the filesystem, neutralizing the blast radius of a future `git add .` slip before any credentials are created.

## Verbatim citations

### 1. Karl Weinmeister (September 2026)
- **Article:** *"Do agent skills help? I ran 72 trials to find out"* (Medium, Sept 2026).
- **Excerpt (Scenario 9, Scoping secret access across projects):**
  > "Cross-project resource sharing introduces a common security trap: granting permissions at the project level instead of the individual resource. In Scenario 9, when asked to allow a Cloud Run service in app-prod to access stripe-webhook-key in sec-vault-prod, the baseline agent frequently suggested project-wide IAM bindings, granting broad access across every secret in the security project. With the plugin, Claude Code scoped the binding strictly to the targeted secret..."

### 2. Felix Fischer, Yasemin Acar, et al. (IEEE S&P 2017)
- **Paper:** *"Stack Overflow Considered Harmful? The Impact of Copy&Paste on Android Application Security"*, 2017 IEEE Symposium on Security and Privacy (SP), pp. 121-136.
- **Finding:** Identified 1,359,302 Android applications on Google Play containing insecure code snippets copied from Stack Overflow.
- **Quotes:**
  > "Unsurprisingly, we observed insecure code snippets being copied into Android applications millions of users install from Google Play every day."
  > "Programming discussions on Stack Overflow are driven by the goal to solve a concrete problem quickly... Security is rarely the main topic of a question."

### 3. Hammond Pearce et al. (IEEE S&P 2022)
- **Paper:** *"Asleep at the Keyboard? Assessing the Security of GitHub Copilot's Code Contributions"*, 2022 IEEE Symposium on Security and Privacy (SP), pp. 754-768.
- **Finding:** Evaluated 1,689 programs generated across 89 CWE scenarios; roughly 40% were vulnerable.
- **Quotes:**
  > "...given the vast quantity of unvetted code that Copilot has processed, it is certain that the language model will have learned from exploitable, buggy code. This raises concerns on the security of Copilot's code contributions."
  > "Where best practices have changed over time, or where the 'easy' way to do something is insecure, Copilot will often suggest the insecure way."

### 4. Neil Perry, Megha Srivastava, Deepak Kumar, and Dan Boneh (ACM CCS 2023)
- **Paper:** *"Do Users Write More Insecure Code with AI Assistants?"*, Proceedings of the 2023 ACM SIGSAC Conference on Computer and Communications Security (CCS '23).
- **Finding:** Developers with access to an AI coding assistant produced significantly more security vulnerabilities across encryption, SQL injection, and path traversal tasks, and were more likely to believe they had written secure code.
