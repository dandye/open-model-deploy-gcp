# Evaluating Agent Graphs for SecOps AI Runbooks

- **Author**: Dan Dye
- **Published**: September 16, 2026
- **Source**: https://security.googlecloudcommunity.com/community-blog-42/evaluating-agent-graphs-for-secops-ai-runbooks-8232
- **Preceding Post**: [Exploring Agent Graphs for SecOps AI Runbooks](https://security.googlecloudcommunity.com/community-blog-42/exploring-agent-graphs-for-secops-ai-runbooks-8113)
- **Related Documentation**: [AI Runbooks for Google SecOps with Model Context Protocol](https://security.googlecloudcommunity.com/community-blog-42/ai-runbooks-for-google-secops-security-operations-with-model-context-protocol-3988)

---

I recently introduced [graph-based agent workflows for Google Security Operations](https://security.googlecloudcommunity.com/community-blog-42/exploring-agent-graphs-for-secops-ai-runbooks-8113) (SecOps) and Google Threat Intelligence and today I want to show some before/after evaluations for those multi-step workflows. My hypothesis was that the graph workflows would consolidate tool calls, reduce tokens, reduce run time, and not decrease quality of the final reports.

All but the last of those are quantitative and easily obtained from the session stats. Report quality is...well, qualitative. We can't hill-climb without a slope though, so I employed rubrics for the qualities of a good investigation/report and tool call trajectory. I used an agent-as-judge to grade against that rubric and produce a final numeric score (0-100).

This work also gave me an opportunity to try out some new [Logstory](https://github.com/chronicle/logstory) scenarios. The [Logstory project](https://github.com/chronicle/logstory) replays security telemetry into a variety of destinations, including Google SecOps.

First, I ran the same scenario three times: prompt-only (no runbooks), AI Runbooks in context, and Graph Workflow. As I'd hoped, runbooks and graph workflows reduce both tokens and runtime.

![Iteration Comparison: Prompt-Only vs AI Runbooks vs Graph Workflow](https://uploads-us-west-2.insided.com/securitygooglecloud-en/attachment/cc5ebe02-82b9-4fab-9f97-5ab5f215a62f.png)

I then repeated the testing with two more scenarios. Here I reported only on the prompt vs graph and I flipped the report to experiments in rows. It was gratifying to see similar improvements for the two additional scenarios!

![Scenario Matrix Comparison: Prompt vs Graph across Multiple Scenarios](https://uploads-us-west-2.insided.com/securitygooglecloud-en/attachment/a3a4b303-d5aa-46a3-bc02-a6715ce0f221.png)

Lastly, I needed those measures of report quality (shown in table below). The letter grades in the Version A: Prompt-Only column (i.e. no runbooks) were a C average and that improved to an A- average with the runbooks. That is expected as the runbooks were initially created to assist with [the LLMs with MCP tool calling](https://security.googlecloudcommunity.com/community-blog-42/ai-runbooks-for-google-secops-security-operations-with-model-context-protocol-3988): "While MCP servers provide the ability to act, the [runbooks] provide guidance on how and when to act."

The runbook to graph testing was intended only to verify graph workflows didn't degrade quality, but they actually eked out a small improvement!

![Report Quality Rubric and Letter Grades](https://uploads-us-west-2.insided.com/securitygooglecloud-en/attachment/276bbb42-2ed0-4967-bffc-a5ec8196be9a.png)

I must admit: that isn't actually all that surprising because these evals are largely ensuring that the tool trajectory is correct and the graph workflows are better at that. That said, having an A/B evaluation system in place unblocks more experimenting, so stay tuned!

---

### Key Context & Integration Takeaways for Part 2

1. **Trajectory vs Skill Isolation**:
   - The Agent Graphs evaluations focused on verifying tool trajectory compliance (correct sequence of investigation steps, token reduction, and runtime consolidation).
   - Part 2 isolates the contribution of **domain skills themselves** (the procedural knowledge, counter-prior rules, and analysis frameworks) using Karl Weinmeister's standardized declarative benchmark (`evals.json`).
2. **Qualitative Evaluation via Agent-as-a-Judge**:
   - Both Part 1 (Agent Graphs) and Part 2 use blinded LLM judges (`gemini-2.5-flash` / `gemini-2.5-pro`) evaluating against explicit rubrics and boolean assertions to quantify qualitative report standards ("we cannot hill-climb without a slope").
3. **Runbooks as MCP Guidance**:
   - "While MCP servers provide the ability to act, runbooks/skills provide guidance on how and when to act."
   - In Part 2, skills serve as counter-priors, overcoming tutorial debt and quickstart antipatterns to enable small open-weight models (8B–14B) to match frontier execution quality.
