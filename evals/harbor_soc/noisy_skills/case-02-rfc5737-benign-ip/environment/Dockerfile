FROM python:3.11-slim

WORKDIR /app

COPY soc_environment.py /app/agent/soc_environment.py
COPY j_init.py /app/agent/__init__.py
COPY jev_judge.py /app/agent/jev_judge.py
COPY jev_evaluator.py /app/agent/jev_evaluator.py
COPY j_init.py /app/scripts/__init__.py
COPY eval_trajectory_verifier.py /app/scripts/eval_trajectory_verifier.py
COPY eval_cost_engine.py /app/scripts/eval_cost_engine.py
COPY soc_sandbox_cli.py /app/scripts/soc_sandbox_cli.py
COPY verify_harbor_soc.py /app/scripts/verify_harbor_soc.py
COPY soc_tier1_interactive.json /app/soc_tier1_interactive.json
COPY soc_tier1_interactive.json /app/configs/evals/gen3/soc_tier1_interactive.json

RUN mkdir -p /var/lib/soc /logs/artifacts /logs/verifier && \
    ln -sf /app/scripts/soc_sandbox_cli.py /usr/local/bin/soc-cli && \
    chmod +x /app/scripts/soc_sandbox_cli.py /app/scripts/verify_harbor_soc.py /usr/local/bin/soc-cli
