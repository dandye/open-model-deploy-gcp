# Pedagogical debt: why web tutorials teach models to over-privilege your cloud, and how skills fix the prior

In his September 2026 benchmark, *"Do agent skills help? I ran 72 trials to find out"*, Karl Weinmeister tested Claude Code across 12 Google Cloud scenarios, with and without the Google Cloud Developer Plugin. Scenario 9 asked the agent to solve a routine production wiring task: allow a Cloud Run service running in project `app-prod` to read a single secret, `stripe-webhook-key`, stored in a dedicated security project named `sec-vault-prod`.

Without the skill plugin, the baseline agent repeatedly reached for a project-level IAM binding. It granted `roles/secretmanager.secretAccessor` across the entire `sec-vault-prod` project, exposing every secret in the security vault to the application service account.

With the plugin loaded, the agent scoped the binding strictly to the target secret:

```bash
PROJECT_ID="sec-vault-prod"
SECRET_ID="stripe-webhook-key"
MEMBER="serviceAccount:runner@app-prod.iam.gserviceaccount.com"
ROLE="roles/secretmanager.secretAccessor"

# Baseline agent completion (project-wide blast radius):
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$MEMBER" \
    --role="$ROLE"

# Skill-guided completion (resource-scoped least privilege):
gcloud secrets add-iam-policy-binding "$SECRET_ID" \
    --project="$PROJECT_ID" \
    --member="$MEMBER" \
    --role="$ROLE"
```

At first glance, this looks like a standard documentation problem. You might assume the baseline model simply did not know the `gcloud secrets add-iam-policy-binding` subcommand and needed a skill to supply the syntax.

That assumption is wrong. Open a clean session with any frontier model and ask directly: *"What is the gcloud command to grant a service account access to one specific Secret Manager secret without granting access to other secrets in the project?"* Every frontier model answers `gcloud secrets add-iam-policy-binding` on the first try. That command has been in the Google Cloud CLI for years. It sits squarely inside pre-training knowledge.

The baseline agent did not fail because of a knowledge deficit. It failed because of a corrupted prior.

## How pedagogical debt becomes the model's default prior

Technical debt is a shortcut an engineer takes to ship working code faster. **Pedagogical debt** is a shortcut a tutorial author takes to get a reader to "Hello World" faster.

Think about the incentives of someone writing a blog post titled *"Build a Stripe Webhook on Cloud Run in 5 Minutes."* The author's goal is to minimize extraneous cognitive load. Every step that is not about Stripe or Cloud Run is friction that might cause the reader to close the tab. Explaining cross-project resource-level IAM policies takes three paragraphs. Tossing `roles/secretmanager.secretAccessor` onto the project takes one line.

We see the exact same shortcut across every domain of software engineering:

- Cloud quickstarts bind `roles/editor` or project-wide `secretAccessor` instead of resource-level roles.
- Linux troubleshooting threads suggest `chmod 777` or `chown -R` to make a permission error disappear.
- Web framework tutorials set `Access-Control-Allow-Origin: *` to get past browser CORS checks during local development.
- Python debugging answers pass `verify=False` to `requests.get()` when a corporate proxy breaks TLS certificate chains.
- Database tutorials interpolate strings directly into SQL queries to keep the example under ten lines.

In human-to-human writing, authors compensate for pedagogical debt by attaching a prose caveat at the bottom of the section: *"Note: For simplicity, we granted project-wide access here. In production, always follow least privilege and bind permissions to the individual secret."*

When we pre-train foundation models on a crawl of the open web, two things happen to that tutorial:

1. **The Hello-World prior swamps the production tail.** For every one production-hardened Terraform repository on GitHub that scopes IAM bindings to individual secret resources, there are hundreds of quickstarts, Medium tutorials, workshop labs, and Stack Overflow answers taking the project-level shortcut. Next-token prediction is a frequency machine. When an agent is mid-trajectory trying to get a Cloud Run deployment working, token generation converges on the statistical mode of the training corpus. The model does not default to how senior security engineers run production infrastructure; it defaults to how bloggers explain a tool in five minutes.
2. **Disclaimer laundering.** In the training document, the over-privileged command lives inside a fenced bash block while the warning ("do not use this in production") sits two paragraphs away in English prose. When the model synthesizes a shell command to satisfy an operational prompt, the high-frequency command template survives and the surrounding caveat is laundered out. What began as a temporary teaching aid becomes an autonomous agent action.

## From copy-paste culture to pre-trained weights

Security researchers documented this exact failure mode in human workflows long before coding agents existed.

In their 2017 IEEE Symposium on Security and Privacy paper, *"Stack Overflow Considered Harmful? The Impact of Copy&Paste on Android Application Security"*, Felix Fischer, Yasemin Acar, and colleagues scanned Google Play and traced insecure code snippets from Stack Overflow into 1.3 million production Android applications. Their explanation of why insecure code dominates Q&A forums applies word-for-word to LLM pre-training corpora:

> *"Programming discussions on Stack Overflow are driven by the goal to solve a concrete problem quickly... Security is rarely the main topic of a question."*

When a developer posts a stack trace caused by a strict security default, the highest-upvoted answer is almost always the fastest snippet that silences the error, such as an empty `X509TrustManager` that accepts any TLS certificate.

Four years later, Hammond Pearce, Baleegh Ahmad, Benjamin Tan, Brendan Dolan-Gavitt, and Ramesh Karri tested what happens when those public code repositories become model weights. In *"Asleep at the Keyboard? Assessing the Security of GitHub Copilot's Code Contributions"* (IEEE S&P 2022), they evaluated 1,689 generated programs across 89 high-risk CWE scenarios and found that roughly 40% contained security vulnerabilities. Crucially, they pointed out that the model is trapped by the frequency of the easy path:

> *"Where best practices have changed over time, or where the 'easy' way to do something is insecure, Copilot will often suggest the insecure way."*

Neil Perry, Megha Srivastava, Deepak Kumar, and Dan Boneh followed up with a controlled user study in *"Do Users Write More Insecure Code with AI Assistants?"* (ACM CCS 2023). Not only did participants with AI assistants write significantly less secure code on tasks where public tutorials commonly cut corners, they also rated their own vulnerable code as *more* secure than the control group did. The model's fluency laundered the tutorial shortcut into something that looked like authoritative engineering.

## Two distinct jobs for agent skills: knowledge injection vs. prior correction

Most conversations about agent skills, MCP servers, and context engineering treat them as vehicles for **knowledge injection**. If a library shipped after the model's knowledge cutoff, or if an organization uses an internal deployment script, you write a skill to give the model facts it does not have in its weights.

Karl Weinmeister's Scenario 9 demonstrates a second, equally important role for skills: **prior correction**.

| Dimension | Knowledge-injection skills | Counter-prior skills |
| :--- | :--- | :--- |
| **Root cause of baseline failure** | The model has never seen the API, flag, or internal tool. | The model knows the safe API, but public tutorials overwhelmingly use an insecure shortcut. |
| **What exists in model weights** | Zero or outdated representations. | Both the production pattern (low probability) and the tutorial shortcut (high probability). |
| **What the skill actually does** | Supplies missing syntax and schemas. | Suppresses the Hello-World prior and forces selection of the low-frequency production pattern. |
| **Classic examples** | Post-cutoff SDKs, internal CLIs, custom enterprise runbooks. | Resource-scoped IAM (`gcloud secrets` vs `gcloud projects`), parameterized SQL, strict TLS, least-privilege IAM roles. |

When you author a counter-prior skill, you are not teaching a novice a new vocabulary word. You are intervening against a bad habit baked into the model by ten thousand introductory tutorials.

## When the Hello-World prior beats your rules file: `git add .` and the leaked `.env` key

Even when you recognize this dynamic and write explicit counter-rules, some tutorial priors are so deeply etched into the weights that soft prompting alone cannot hold them back.

My own sharpest scar here is `git add .`.

Every "Get Started with Git" guide, every framework quickstart, and every "Deploy in 5 Minutes" blog post on the internet ends with the same three-line ritual:

```bash
COMMIT_MSG="Initial commit"

# What every tutorial on Earth teaches:
git add .
git commit -m "$COMMIT_MSG"
git push
```

Tutorial authors write `git add .` because they assume the reader is working inside a fresh, empty directory created three minutes earlier. In a real engineering workspace, the working tree is full of untracked scratch scripts, local debug dumps, and `.env` files holding live credentials used to test integrations.

Because of that, I strictly forbid `git add .` in my agent rules files (`AGENTS.md` and `GEMINI.md`), instructing agents to inspect `git status` and stage only explicit file paths:

```bash
TARGET_FILE="src/client.py"
TEST_FILE="tests/test_client.py"
COMMIT_MSG="feat(client): add retry backoff"

# Production workflow required by rules files:
git status --short
git add "$TARGET_FILE" "$TEST_FILE"
git commit -m "$COMMIT_MSG"
```

Despite having that prohibition in my rules files, I still had an agent run `git add .`, sweep up a local `.env` file containing a live API key, commit it, and push it to the remote repository. I had to immediately revoke and rotate the key and scrub the history. It was deeply embarrassing, especially as someone who builds security tooling for a living.

Why did the agent ignore an explicit rule forbidding `git add .`? Two mechanisms compound at the end of an agent trajectory:

1. **Fused macro sequences in pre-training.** In millions of public shell transcripts and tutorials, `git add . && git commit -m ... && git push` appears as a single idiomatic unit meaning "wrap up and ship." Once the agent decides the coding task is finished, the transitional probability from "tests passed, time to commit" to `git add .` is overwhelming.
2. **Finish-line context decay.** Rules files (`AGENTS.md`) are injected at the very top of the context window. By the time an agent has spent forty tool calls diagnosing an API error, writing a `.env` file to test against a live endpoint, and iterating on pytest failures, tens of thousands of tokens of stack traces and file diffs sit between the system rules and the current step. Right at the finish line, when the `.env` file is sitting untracked on disk, the distant negative prompt loses the tug-of-war against pre-trained muscle memory.

## Three jobs for agent skills: knowledge injection, counter-prior steering, and commit-zero scaffolding

Putting Karl Weinmeister's Scenario 9 next to the `git add .` failure gives us a sharper taxonomy of what agent skills actually do. Most teams think skills only do one job, supplying missing facts. In practice, defending an engineering workflow against tutorial bias requires three distinct kinds of skills:

| Skill archetype | When it acts | What it changes | How it handles tutorial shortcuts |
| :--- | :--- | :--- | :--- |
| **1. Knowledge-injection skills** | During task planning | Supplies post-cutoff APIs, internal CLI flags, or private schemas missing from model weights. | Does not address shortcuts; assumes the model simply lacks the syntax. |
| **2. Counter-prior skills** (`google-cloud` plugin) | During code & CLI generation | Suppresses high-frequency tutorial shortcuts (`gcloud projects`) in favor of safer low-frequency APIs (`gcloud secrets`). | Probabilistic steering. Shifts compliance from ~20% to ~95%, which wins benchmarks, but can still decay over long contexts. |
| **3. Commit-zero scaffolding skills** (`skel`) | At project initialization (Step 0) | Lays down deterministic filesystem guardrails (`.gitignore` with `.env`, `.env.example`, `AGENTS.md`, `justfile`) before work begins. | Structural immunity. Even if finish-line context decay causes the agent to run `git add .` at step 50, Git itself refuses to stage `.env`. |

That third category is the direct lesson from my leaked API key. After having an agent commit `.env` despite my rules file, I built my `skel` skill so that every new repository starts life with `.env`, `.env.*`, `*.pem`, and `*credentials*.json` baked into `.gitignore` at commit zero, paired with a committed `.env.example` template:

```bash
PROJECT_NAME="my-service"

# Bootstrap repository with .gitignore (.env excluded), AGENTS.md, and worktree layout at step 0:
~/.gemini/config/skills/skel/scripts/skel.sh "$PROJECT_NAME"
```

Notice why a scaffolding skill succeeds where a prompt rule alone fails. Asking a model to obey *"never run `git add .`"* at the end of a forty-step debugging session forces a probabilistic tug-of-war in token space right when context dilution is worst. Using the `skel` skill at step zero moves the defense out of token space and into the Git index. Fifty turns later, when the agent's pre-trained tutorial reflex fires and it runs `git add .`, the `.gitignore` written at commit zero catches the `.env` file deterministically.

## Designing skills and harnesses against pedagogical debt

If you are building skills and harnesses for coding agents, assume from day one that your model wants to write code like a five-minute quickstart:

1. **Write counter-prior skills that name the shortcut explicitly.** Showing the resource-level command in a positive example is not enough. Because the project-level command has such high prior probability in the weights, forbid the shortcut by name: *"Never bind `roles/secretmanager.secretAccessor` at the project level (`gcloud projects add-iam-policy-binding`). Always bind at the secret resource level (`gcloud secrets add-iam-policy-binding`)."*
2. **Re-attach the laundered blast radius.** State the concrete operational consequence that tutorials omit: project-level binding exposes every secret in the vault project to the caller; wildcard `git add .` sweeps untracked `.env` credentials into commit history.
3. **Benchmark skills on tasks where the model already knows the API.** If you only evaluate skills on brand-new APIs, you only measure knowledge injection. Evaluating on cross-project secret scoping, IAM role selection, and git staging measures whether your skills can overpower the internet's pedagogical debt.
4. **Use scaffolding skills (`skel`) and pre-tool hooks for zero-tolerance invariants.** When a 5% residual slip rate means rotating production API keys, do not rely on a distant line in `AGENTS.md` to win every time. Use a scaffolding skill like `skel` to put `.env` into `.gitignore` before the first line of application code is written, and back it with harness pre-tool hooks that reject `git add .` and `git add -A` outright.

Tutorials will always optimize for time-to-Hello-World, and pre-training corpora will always inherit that bias. Counter-prior skills steer the model away from what a million quickstarts taught it to do; scaffolding skills like `skel` ensure that when the tutorial reflex still slips through, your secrets stay on disk.
