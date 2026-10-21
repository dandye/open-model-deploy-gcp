"""Unit tests for Track 2 Proactive Threat Hunting Environment, Agent Hooks, and Suite Verifier."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from agent.hierarchical_soc_agent import (
    HierarchicalSOCTier1Agent,
    SOCRunbookWorkerAgent,
    WorkerInvestigationReport,
)
from agent.soc_tier1_agent import SocDecision
from agent.threat_hunt_environment import (
    BENIGN_NGINX_HTML_SHA256,
    LOLBIN_RUNDLL32_SHA256,
    PATIENT_ZERO_HOST,
    ThreatHuntEnvironment,
    UNALERTED_SOAR_CASE_ID,
    URSNIF_COLLECTION_ID,
    URSNIF_DLL_SHA256,
    URSNIF_PAYLOAD_SHA256,
    URSNIF_PRIMARY_C2_DOMAIN,
)
from scripts.eval_threat_hunt_multi_model import (
    DEFAULT_SUITE_PATH,
    analyze_hunt_trajectory,
    load_arm_config,
)
from scripts.evolve_threat_hunt_harness2 import (
    HUNT_COMPONENT_NAME,
    ThreatHuntGEPAAdapter,
    run_threat_hunt_harness2_evolution,
)
from scripts.verify_harbor_soc import compose_soc_reward
import gepa
import tempfile


class TestThreatHuntEnvironmentAndAgent(unittest.TestCase):
  """Tests Track 2 ThreatHuntEnvironment and HierarchicalSOCTier1Agent threat-hunt wiring."""

  def setUp(self) -> None:
    self.suite = json.loads(DEFAULT_SUITE_PATH.read_text(encoding="utf-8"))
    self.scenarios = {s["eval_id"]: s for s in self.suite["scenarios"]}

  def test_collection_and_domain_pivot_tools(self) -> None:
    case = self.scenarios["HUNT-URSNIF-COLLECTION-01"]
    env = ThreatHuntEnvironment(initial_state=case["initial_state"])

    col_rep = env.query_tool(
        "get_collection_report", {"collection_id": URSNIF_COLLECTION_ID}
    )
    self.assertEqual(col_rep["status"], "SUCCESS")
    self.assertIn("Ursnif", col_rep["threat_family"])

    rel_rep = env.query_tool(
        "get_entities_related_to_a_collection",
        {"collection_id": URSNIF_COLLECTION_ID, "relationship_name": "all"},
    )
    self.assertEqual(rel_rep["status"], "SUCCESS")
    self.assertIn(URSNIF_PRIMARY_C2_DOMAIN, rel_rep["domains"])
    file_hashes = [f["sha256"] for f in rel_rep["files"]]
    self.assertIn(URSNIF_PAYLOAD_SHA256, file_hashes)
    self.assertIn(LOLBIN_RUNDLL32_SHA256, file_hashes)

    dom_piv = env.query_tool(
        "get_entities_related_to_a_domain",
        {"domain": URSNIF_PRIMARY_C2_DOMAIN, "relationship_name": "communicating_files"},
    )
    self.assertEqual(dom_piv["status"], "SUCCESS")
    piv_hashes = [f["sha256"] for f in dom_piv["communicating_files"]]
    self.assertIn(URSNIF_DLL_SHA256, piv_hashes)
    self.assertIn(BENIGN_NGINX_HTML_SHA256, piv_hashes)

  def test_horizon_widening_72h_to_168h(self) -> None:
    case = self.scenarios["HUNT-URSNIF-COLLECTION-01"]
    env = ThreatHuntEnvironment(initial_state=case["initial_state"])

    ioc_72 = env.query_tool("get_ioc_matches", {"hours_back": 72})
    self.assertEqual(ioc_72["total_matches"], 0)
    self.assertIn("168", ioc_72["hint"])

    ioc_168 = env.query_tool("get_ioc_matches", {"hours_back": 168})
    self.assertGreater(ioc_168["total_matches"], 0)

    ev_72 = env.query_tool(
        "search_security_events",
        {"query": URSNIF_PRIMARY_C2_DOMAIN, "hours_back": 72},
    )
    self.assertEqual(ev_72["total_events"], 0)

    ev_168 = env.query_tool(
        "search_security_events",
        {"query": URSNIF_PRIMARY_C2_DOMAIN, "hours_back": 168},
    )
    self.assertGreater(ev_168["total_events"], 0)

    ev_colon = env.query_tool(
        "search_security_events",
        {"query": f"hash:{URSNIF_DLL_SHA256} OR domain:{URSNIF_PRIMARY_C2_DOMAIN}", "hours_back": 168},
    )
    self.assertGreater(ev_colon["total_events"], 0)

  def test_mcp_prefix_and_escaped_quotes_normalization(self) -> None:
    case = self.scenarios["HUNT-URSNIF-COLLECTION-01"]
    env = ThreatHuntEnvironment(initial_state=case["initial_state"])
    worker = SOCRunbookWorkerAgent(
        classification="THREAT_HUNT",
        runbook_name="gti_collection_threat_hunt.md",
        runbook_content="Step 1: get_collection_report",
        project_id="test-proj",
        environment=env,
    )
    parsed_dot = worker._parse_action(
        f'Action: gti-mcp.get_collection_report(collection_id="{URSNIF_COLLECTION_ID}")'
    )
    self.assertEqual(parsed_dot, ("get_collection_report", {"collection_id": URSNIF_COLLECTION_ID}))

    parsed_wrap = worker._parse_action(
        f'Action: gti-mcp(get_collection_report="{URSNIF_COLLECTION_ID}")'
    )
    self.assertEqual(parsed_wrap, ("get_collection_report", {"collection_id": URSNIF_COLLECTION_ID}))

    parsed_escaped = worker._parse_action(
        'Action: search_security_events(query="principal.ip = \\"193.106.191.163\\" OR dns.question.name = \\"superstarts.top\\"", hours_back=168)'
    )
    self.assertIsNotNone(parsed_escaped)
    self.assertEqual(parsed_escaped[0], "search_security_events")
    self.assertIn("superstarts.top", parsed_escaped[1]["query"])

  def test_supervisor_classification_and_target_resolution(self) -> None:
    case = self.scenarios["HUNT-URSNIF-COLLECTION-01"]
    env = ThreatHuntEnvironment(initial_state=case["initial_state"])
    sup = HierarchicalSOCTier1Agent(
        project_id="test-proj",
        environment=env,
        use_runbooks=True,
    )
    self.assertEqual(sup.classify_alert(case["prompt"]), "THREAT_HUNT")
    self.assertEqual(
        sup.get_runbook_for_classification("THREAT_HUNT"),
        "gti_collection_threat_hunt.md",
    )

    worker = SOCRunbookWorkerAgent(
        classification="THREAT_HUNT",
        runbook_name="gti_collection_threat_hunt.md",
        runbook_content="Step 1: get_collection_report",
        project_id="test-proj",
        environment=env,
    )
    self.assertTrue(worker._is_tool_allowed("get_collection_report"))
    self.assertTrue(worker._is_tool_allowed("get_entities_related_to_a_collection"))
    self.assertTrue(worker._is_tool_allowed("get_entities_related_to_a_domain"))
    self.assertTrue(worker._is_tool_allowed("get_ioc_matches"))
    self.assertTrue(worker._is_tool_allowed("search_security_events"))
    self.assertFalse(worker._is_tool_allowed("isolate_host"))

    report = WorkerInvestigationReport(
        classification="THREAT_HUNT",
        runbook_name="gti_collection_threat_hunt.md",
        target_entities=[
            URSNIF_COLLECTION_ID,
            URSNIF_PRIMARY_C2_DOMAIN,
            LOLBIN_RUNDLL32_SHA256,
            URSNIF_DLL_SHA256,
            PATIENT_ZERO_HOST,
            UNALERTED_SOAR_CASE_ID,
        ],
        findings={},
        evidence=[
            f"search_security_events: host {PATIENT_ZERO_HOST} queried {URSNIF_PRIMARY_C2_DOMAIN} in {UNALERTED_SOAR_CASE_ID}"
        ],
        risk_level="MALICIOUS",
        raw_response=f"Host {PATIENT_ZERO_HOST} compromised via {URSNIF_PRIMARY_C2_DOMAIN} and {URSNIF_DLL_SHA256} ({UNALERTED_SOAR_CASE_ID}).",
    )
    decision = SocDecision(
        verdict="MALICIOUS",
        recommended_actions=["isolate_host", "block_indicator", "update_case_comment"],
        target_entity=PATIENT_ZERO_HOST,
        rationale="Active Ursnif compromise on malwaretest-win.",
    )

    resolved_host = sup._resolve_target_host(decision, report, case["prompt"])
    self.assertEqual(resolved_host, PATIENT_ZERO_HOST)

    resolved_ind = sup._resolve_target_indicator(decision, report, case["prompt"])
    self.assertEqual(resolved_ind, URSNIF_PRIMARY_C2_DOMAIN)
    self.assertNotEqual(resolved_ind, LOLBIN_RUNDLL32_SHA256)

    resolved_case = sup._resolve_target_case(case["prompt"], decision, report)
    self.assertEqual(resolved_case, UNALERTED_SOAR_CASE_ID)

  def test_analyze_hunt_trajectory_and_harbor_reward(self) -> None:
    case = self.scenarios["HUNT-URSNIF-COLLECTION-01"]
    trajectory = [
        {
            "iteration": 1,
            "agent": "worker",
            "tool": "get_entities_related_to_a_collection",
            "args": {"collection_id": URSNIF_COLLECTION_ID, "relationship_name": "all"},
            "observation": json.dumps({"domains": [URSNIF_PRIMARY_C2_DOMAIN]}),
        },
        {
            "iteration": 2,
            "agent": "worker",
            "tool": "search_security_events",
            "args": {"query": URSNIF_PRIMARY_C2_DOMAIN, "hours_back": 72},
            "observation": json.dumps({"total_events": 0, "hours_back": 72}),
        },
        {
            "iteration": 3,
            "agent": "worker",
            "tool": "search_security_events",
            "args": {"query": URSNIF_PRIMARY_C2_DOMAIN, "hours_back": 168},
            "observation": json.dumps({"total_events": 27, "hours_back": 168, "hostname": PATIENT_ZERO_HOST}),
        },
        {
            "iteration": 4,
            "agent": "worker",
            "tool": "get_file_report",
            "args": {"hash": LOLBIN_RUNDLL32_SHA256},
            "observation": json.dumps({"verdict": "BENIGN", "vendor": "Microsoft Corporation"}),
        },
        {
            "iteration": 5,
            "agent": "supervisor",
            "tool": "isolate_host",
            "args": {"hostname": PATIENT_ZERO_HOST},
            "observation": json.dumps({"status": "SUCCESS"}),
        },
        {
            "iteration": 6,
            "agent": "supervisor",
            "tool": "block_indicator",
            "args": {"indicator": URSNIF_PRIMARY_C2_DOMAIN},
            "observation": json.dumps({"status": "SUCCESS"}),
        },
        {
            "iteration": 7,
            "agent": "supervisor",
            "tool": "update_case_comment",
            "args": {"case_id": UNALERTED_SOAR_CASE_ID, "comment": "Contained Ursnif on malwaretest-win."},
            "observation": json.dumps({"status": "SUCCESS"}),
        },
    ]
    report_text = (
        f"[Context & Enrichment]\nHost {PATIENT_ZERO_HOST} queried {URSNIF_PRIMARY_C2_DOMAIN} ({UNALERTED_SOAR_CASE_ID}).\n"
        "[Analysis & Verdict]\nMALICIOUS\n"
    )
    harbor_info = compose_soc_reward(
        case=case,
        trajectory=trajectory,
        report_text=report_text,
        decision_data={
            "verdict": "MALICIOUS",
            "recommended_actions": ["isolate_host", "block_indicator", "update_case_comment"],
        },
        jev_backend_name="mock",
    )
    metrics = analyze_hunt_trajectory(
        case=case,
        trajectory=trajectory,
        report_text=report_text,
        actual_verdict="MALICIOUS",
        harbor_breakdown=harbor_info,
    )
    self.assertTrue(metrics["widened_168h"])
    self.assertTrue(metrics["verified_lolbin_hash"])
    self.assertTrue(metrics["discovered_patient_zero"])
    self.assertEqual(metrics["hunt_composite_score"], 1.0)
    self.assertGreaterEqual(harbor_info["reward"], 0.95)

  def test_threat_hunt_harness2_evolution_and_arm_loader(self) -> None:
    """Verify k=2 Harness^2 threat-hunt evolution loop and harness2_evolved_hunt arm loader."""
    with tempfile.TemporaryDirectory() as tmp:
      tmp_dir = Path(tmp)

      class _MockHuntAdapter(ThreatHuntGEPAAdapter):
        def evaluate(self, batch, candidate, capture_traces=False):
          text = candidate.get(HUNT_COMPONENT_NAME, "")
          ck = self._cand_key(candidate)
          self._telemetry_cache.setdefault(ck, {})
          scores = []
          trajs = []
          for c in batch:
            cid = str(c.get("eval_id"))
            score = 0.85
            if "list_cases" in text and "get_file_report" in text and "EVERY candidate file hash" in text:
              score = 1.0
            elif "list_cases" in text and cid == "HUNT-DEGRADED-503-04":
              score = 0.98
            t = {
                "case_id": cid,
                "eval_id": cid,
                "component_name": HUNT_COMPONENT_NAME,
                "alert_type": "THREAT_HUNT",
                "prompt": c["prompt"],
                "expected_verdict": c["ground_truth_label"],
                "actual_verdict": c["ground_truth_label"],
                "expected_actions": list(c.get("expected_actions", [])),
                "prohibited_actions": list(c.get("prohibited_actions", [])),
                "executed_actions": list(c.get("expected_actions", [])),
                "score": score,
                "hunt_composite_score": score,
                "harbor_reward": score,
                "loss_penalty": 1.0,
                "assert_passed": True,
                "safety_gate_triggered": False,
                "zero_tool_hesitation": False,
                "inert": False,
                "tool_calls": 5,
                "epistemic_steps": 3,
                "failure_category": "FLAWLESS_CONTAINMENT" if score >= 0.95 else "DEGRADED_MODE_FAILURE",
                "hunt_metrics": {
                    "verdict_ok": True,
                    "operator_ok": score >= 0.95,
                    "widened_168h": True,
                    "verified_lolbin_hash": score >= 0.99,
                },
                "summary": "mock summary",
            }
            self._telemetry_cache[ck][cid] = t
            scores.append(score)
            trajs.append(t)
          return gepa.EvaluationBatch(
              outputs=["mock"] * len(batch),
              scores=scores,
              trajectories=trajs if capture_traces else None,
          )

      def _fake_reflection_lm(prompt: str) -> str:
        base_rb = load_arm_config("compressed_track_b_hunt")["runbooks_dict"][HUNT_COMPONENT_NAME]
        if "You are the INVARIANT (INV)" in prompt:
          return (
              "```markdown\n"
              + base_rb
              + "\n- On HTTP 503 outage, call list_cases once to verify open <case_id> before update_case_comment.\n```"
          )
        if "You are the DOMAIN (DOM)" in prompt:
          return (
              "```markdown\n"
              + base_rb
              + "\n- Call get_file_report on EVERY candidate file hash before Stage C containment.\n```"
          )
        return (
            "```markdown\n"
            + base_rb
            + "\n- On HTTP 503 outage, call list_cases once to verify open <case_id> before update_case_comment."
            + "\n- Call get_file_report on EVERY candidate file hash before Stage C containment.\n```"
        )

      seed_rb = load_arm_config("compressed_track_b_hunt")["runbooks_dict"][HUNT_COMPONENT_NAME]
      mock_adapter = _MockHuntAdapter(seed_candidate={HUNT_COMPONENT_NAME: seed_rb})
      meta = run_threat_hunt_harness2_evolution(
          output_dir=tmp_dir,
          rounds=2,
          reflection_lm_override=_fake_reflection_lm,
          adapter_override=mock_adapter,
      )
      self.assertTrue(meta["promoted"])
      self.assertGreater(meta["best_score"], meta["baseline_score"])
      evolved_file = tmp_dir / HUNT_COMPONENT_NAME
      self.assertTrue(evolved_file.exists())

      arm_cfg = load_arm_config("harness2_evolved_hunt", evolved_hunt_path=evolved_file)
      self.assertTrue(arm_cfg["use_runbooks"])
      self.assertIn("EVERY candidate file hash", arm_cfg["runbooks_dict"][HUNT_COMPONENT_NAME])


if __name__ == "__main__":
  unittest.main()
