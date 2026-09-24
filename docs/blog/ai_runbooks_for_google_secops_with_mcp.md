# AI Runbooks for Google SecOps: Security Operations with Model Context Protocol

- **Author**: Dan Dye
- **Published**: June 2025 / Community Blog
- **Source**: https://security.googlecloudcommunity.com/community-blog-42/ai-runbooks-for-google-secops-security-operations-with-model-context-protocol-3988
- **Repository**: [github.com/dandye/ai-runbooks](https://github.com/dandye/ai-runbooks)
- **Subsequent Blog Posts**:
  - [Exploring Agent Graphs for SecOps AI Runbooks](exploring_agent_graphs_for_secops_ai_runbooks.md)
  - [Evaluating Agent Graphs for SecOps AI Runbooks](evaluating_agent_graphs_for_secops_ai_runbooks.md)
  - [Serving Open Models for Security Agents, Part 2: Do Domain Skills Actually Help Open Models?](part2_evaluating_agent_skills_across_model_scales.md)

---

Google [recently introduced Model Context Protocol (MCP) Servers for Google Security Operations (SecOps)](https://www.googlecloudcommunity.com/gc/Community-Blog/Building-an-open-ecosystem-for-AI-driven-security-with-MCP/ba-p/898843), Google Threat Intelligence (GTI), and Google Security Command Center (SCC). They are run locally and you can interact with them from clients like Google’s Agent Development Kit (ADK) or Anthropic’s Claude. My own preference is to run them from an Integrated Development Environment (IDE) like Cursor, Windsurf, Roo, or what I will demo here: Cline.

I prefer the IDE for several reasons. I have the MCP servers and Large Language Model (LLM) generate markdown documents for each research and analysis interaction. The IDE makes it easy to get a rich preview of those markdown documents and also to commit them to my source control (git). Secondly, my first prompts were typed into the Cline message box, but I quickly realized that I needed them in a text editor as I needed to iterate on them. That quickly evolved into something of an existing best practice for security operations centers: runbooks.

So today, I’m introducing a [collection of these runbooks and their supporting files](https://github.com/dandye/ai-runbooks). These are not meant for production use, but rather to showcase the potential of AI runbooks. The runbooks are all currently stored in the .clinerules directory of the GitHub project, so that they are in the context window for every interaction.

![image](https://uploads-us-west-2.insided.com/securitygooglecloud-en/attachment/146440i2C89D153589D8C85.png)[https://github.com/dandye/ai-runbooks](https://github.com/dandye/ai-runbooks)

# Bridging the Gap: MCP Servers for Security Tools

Before diving into that .clinerules directory, let's talk about the new MCP servers used by this project. MCP allows LLMs to interact directly with external tools and data sources in a standardized way. Google’s new security-focused MCP servers are:

- **secops-mcp****:** Provides tools for interacting directly with Google SecOps SIEM (e.g., searching events, looking up entities, getting alerts).
- **secops-soar****:** Enables interaction with Google SecOps SOAR for case management, playbook actions, and orchestration. Extensible via marketplace integrations.
- **gti-mcp****:** Offers access to the rich dataset of Google Threat Intelligence for IOC enrichment, threat actor research, and vulnerability context.
- **scc-mcp****:** Allows querying Google Security Command Center for cloud security posture findings.

These servers give our LLM the ability to perform real security actions and gather critical data directly from the platforms analysts use daily.

# Introducing AI Runbooks: Guiding the AI

While MCP servers provide the *ability* to act, the .clinerules directory provides the *guidance* on *how* and *when* to act. Located at the root of the project, this directory serves as a knowledge base, codifying operational context, standard procedures, and role-specific perspectives for the LLM.

The goal is to make the LLM more effective, consistent, and aligned with our specific security environment and practices.

## Personas and Runbooks

The primary types of guidance are:

1. **Personas (**[./personas/](https://github.com/dandye/ai-runbooks/tree/main/.clinerules/personas)**)**
2. **Runbooks (**[./run_books/](https://github.com/dandye/ai-runbooks/tree/main/.clinerules/run_books)**)**

# The Synergy: Run Books + MCP Servers

To recap:

- **Personas** help the LLM understand *who* is asking and *what* they likely need.
- **Runbooks** tell the LLM *how* to achieve a specific goal using the available tools.
- **MCP Servers** provide the *actual tools* (like gti-mcp.get_file_report or secops-mcp.search_security_events) that the LLM uses, guided by the runbooks and personas.

This synergy enables the LLM to operate more like an experienced analyst, following best practices and leveraging specialized tools effectively within our specific operational context.

## What’s Next?

I’ve added a lot of planning documents to the project. For example, the .clinerules/readme.md also outlines suggestions for future context files, including network maps, asset inventory guidelines, tool configurations, organizational policies, and internal threat profiles. Adding these will further enhance the LLM’s environmental awareness and decision-making capabilities. I want to note that much of this planning, like the other content, came directly from Gemini 2.5 itself, by iteratively executing the runbooks and then asking the LLM, “how could we improve this process?”

Below is a brief video of that kind of interaction.

Execute and Improve APT Hunt Runbook YouTube video.

# Conclusion

The use of runbooks with the new security-focused MCP servers represents a significant step forward in making LLM powerful allies in the SOC. By providing structured guidance, operational context, and direct access to security platforms, we can improve the consistency, speed, and effectiveness of our security operations. Check out the introduction video below and explore the .clinerules directory in the [GitHub repo](http://goo.gle/ai-runbooks) to see these concepts in action!
