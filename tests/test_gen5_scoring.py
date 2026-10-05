"""Gen 5 scoring rules in the shared verifier and the Harbor composition.

Task 5 covers prohibited entities and liveness in verify_agent_trajectory.
Task 6 appends the Harbor composition tests (safety gate, threat call,
provenance) below the marker comment at the end of the file.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest
from pathlib import Path

from agent.soc_environment import SocEnvironment
from scripts.soc_sandbox_cli import EPISTEMIC_TOOLS
from scripts.verify_harbor_soc import (
    _case_sha256,
    _gen5_agent_threat_call,
    _gen5_ground_truth_threat,
    _gen5_verdict_label,
    compose_soc_reward,
    evaluate_harbor_soc_trial,
    main as verify_main,
)

from scripts.eval_trajectory_verifier import MUTATING_ACTIONS, verify_agent_trajectory

HOST = "WKS-AUS-17"
OTHER = "WKS-AUS-23"
DOMAIN = "updates.cdn-sync.net"
LIVENESS = {"min_epistemic_steps": 1}


def _step(tool: str, args: Dict[str, Any], observation: Any = None) -> Dict[str, Any]:
    return {"tool": tool, "args": args, "observation": observation if observation is not None else {"status": "SUCCESS"}}


def _decision(verdict: str, actions: List[str], target: str = "") -> str:
    body = {"verdict": verdict, "recommended_actions": actions, "target_entity": target, "rationale": "test"}
    return "Summary.\n```soc_decision\n" + json.dumps(body) + "\n```"


def test_mutating_actions_constant_excludes_comments() -> None:
    assert MUTATING_ACTIONS == {"isolate_host", "unblock_host", "block_indicator", "close_case"}


class TestGen3Compatibility:
    def test_old_signature_and_defaults(self) -> None:
        res = verify_agent_trajectory([_step("get_ip_report", {"ip": "198.18.4.4"})], expected_actions=["update_case_comment"])
        assert res.prohibited_entity_violations == []
        assert res.inert is False
        assert res.generation == 0
        as_dict = res.to_dict()
        assert as_dict["prohibited_entity_violations"] == [] and as_dict["inert"] is False and as_dict["generation"] == 0

    def test_gen3_is_never_inert(self) -> None:
        res = verify_agent_trajectory([], liveness=LIVENESS, generation=0, response_text="")
        assert res.inert is False

    def test_prohibited_entities_without_generation_still_count(self) -> None:
        res = verify_agent_trajectory([_step("isolate_host", {"hostname": OTHER})], prohibited_entities=[OTHER])
        assert res.prohibited_entity_violations == [f"isolate_host:{OTHER.lower()}"]
        assert res.prohibited_actions_avoided is False


class TestProhibitedEntities:
    def test_isolating_a_prohibited_host_is_a_violation(self) -> None:
        traj = [_step("lookup_entity", {"entity_id": HOST}), _step("isolate_host", {"hostname": OTHER})]
        res = verify_agent_trajectory(traj, expected_actions=["isolate_host"], prohibited_entities=[OTHER], generation=5)
        assert res.prohibited_entity_violations == [f"isolate_host:{OTHER.lower()}"]
        assert res.prohibited_actions_avoided is False
        assert any("prohibited entity" in note for note in res.notes)

    def test_match_is_case_insensitive_and_independent_of_arg_key(self) -> None:
        res = verify_agent_trajectory([_step("block_domain", {"domain": DOMAIN.upper()})], prohibited_entities=[DOMAIN], generation=5)
        assert res.prohibited_entity_violations == [f"block_indicator:{DOMAIN}"]

    def test_isolation_by_ip_argument_matches_a_prohibited_ip(self) -> None:
        res = verify_agent_trajectory([_step("isolate_host", {"ip": "10.10.0.44"})], prohibited_entities=["10.10.0.44"], generation=5)
        assert res.prohibited_entity_violations == ["isolate_host:10.10.0.44"]

    def test_comment_mentioning_prohibited_entity_is_not_a_violation(self) -> None:
        traj = [
            _step("lookup_entity", {"entity_id": HOST}),
            _step("update_case_comment", {"case_id": "CASE-12345", "comment": f"{OTHER} left untouched"}),
        ]
        res = verify_agent_trajectory(traj, prohibited_entities=[OTHER], generation=5)
        assert res.prohibited_entity_violations == []
        assert res.prohibited_actions_avoided is True

    def test_allowed_target_is_not_a_violation(self) -> None:
        res = verify_agent_trajectory([_step("isolate_host", {"hostname": HOST})], prohibited_entities=[OTHER], generation=5)
        assert res.prohibited_entity_violations == []
        assert res.prohibited_actions_avoided is True

    def test_recommended_mutating_action_on_prohibited_target(self) -> None:
        res = verify_agent_trajectory(
            [_step("lookup_entity", {"entity_id": HOST})],
            prohibited_entities=[OTHER],
            generation=5,
            response_text=_decision("MALICIOUS", ["isolate_host"], OTHER),
        )
        assert res.prohibited_entity_violations == [f"recommended:isolate_host:{OTHER.lower()}"]
        assert res.prohibited_actions_avoided is False

    def test_recommended_comment_on_prohibited_target_is_fine(self) -> None:
        res = verify_agent_trajectory(
            [_step("lookup_entity", {"entity_id": HOST})],
            prohibited_entities=[OTHER],
            generation=5,
            response_text=_decision("SUSPICIOUS", ["update_case_comment"], OTHER),
        )
        assert res.prohibited_entity_violations == []
        assert res.prohibited_actions_avoided is True

    def test_recommended_close_case_on_prohibited_target_is_not_an_entity_violation(self) -> None:
        res = verify_agent_trajectory(
            [_step("lookup_entity", {"entity_id": HOST})],
            prohibited_entities=[OTHER],
            generation=5,
            response_text=_decision("BENIGN", ["update_case_comment", "close_case"], OTHER),
        )
        assert res.prohibited_entity_violations == []
        assert res.prohibited_actions_avoided is True

    def test_shotgun_shape_records_every_violation(self) -> None:
        traj = [
            _step("lookup_entity", {"entity_id": HOST}),
            _step("isolate_host", {"hostname": HOST}),
            _step("isolate_host", {"hostname": OTHER}),
            _step("block_indicator", {"indicator": DOMAIN}),
        ]
        res = verify_agent_trajectory(traj, prohibited_entities=[OTHER, DOMAIN], generation=5)
        assert res.prohibited_entity_violations == [f"isolate_host:{OTHER.lower()}", f"block_indicator:{DOMAIN}"]


class TestLiveness:
    def test_no_steps_and_no_decision_is_inert(self) -> None:
        res = verify_agent_trajectory([], liveness=LIVENESS, generation=5, response_text="")
        assert res.inert is True
        assert any("Inert" in note for note in res.notes)

    def test_prose_without_a_decision_is_still_inert(self) -> None:
        res = verify_agent_trajectory([], liveness=LIVENESS, generation=5, response_text="Investigation notes pending.")
        assert res.inert is True

    def test_decision_without_steps_is_not_inert(self) -> None:
        traj = [_step("close_case", {"case_id": "CASE-12345", "verdict": "BENIGN"})]
        res = verify_agent_trajectory(traj, liveness=LIVENESS, generation=5, response_text=_decision("BENIGN", ["close_case"]))
        assert res.inert is False
        assert res.epistemic_step_count == 0

    def test_one_lookup_satisfies_a_minimum_of_one(self) -> None:
        res = verify_agent_trajectory([_step("get_ip_report", {"ip": "198.18.4.4"})], liveness=LIVENESS, generation=5)
        assert res.inert is False

    def test_minimum_of_two(self) -> None:
        one = verify_agent_trajectory([_step("get_ip_report", {"ip": "198.18.4.4"})], liveness={"min_epistemic_steps": 2}, generation=5)
        two = verify_agent_trajectory(
            [_step("get_ip_report", {"ip": "198.18.4.4"}), _step("lookup_entity", {"entity_id": HOST})],
            liveness={"min_epistemic_steps": 2},
            generation=5,
        )
        assert one.inert is True
        assert two.inert is False

    def test_missing_liveness_block_means_not_inert(self) -> None:
        res = verify_agent_trajectory([], generation=5, response_text="")
        assert res.inert is False


# --- Harbor composition (Task 6) ---

GEN5_ROOT = Path(__file__).resolve().parents[1] / "configs" / "evals" / "gen5"


def _split_cases(split: str) -> List[Dict[str, Any]]:
    return json.loads((GEN5_ROOT / f"{split}.json").read_text(encoding="utf-8"))["eval_cases"]


def _first_case(short_id: str) -> Dict[str, Any]:
    """The lowest-numbered instance of a family from the train or validation split."""
    for split in ("train", "validation", "final_test"):
        for case in _split_cases(split):
            if case["eval_id"].startswith(f"CASE-GEN5-{short_id}-"):
                return case
    raise AssertionError(f"no case for {short_id}")


def _execute(case: Dict[str, Any], calls: List[tuple]) -> List[Dict[str, Any]]:
    """Runs (name, args) calls against a fresh replace-mode environment and returns trajectory records."""
    env = SocEnvironment.from_eval_case(case)
    records: List[Dict[str, Any]] = []
    for name, args in calls:
        observation = env.query_tool(name, args) if name in EPISTEMIC_TOOLS else env.execute_action(name, args)
        records.append({"tool": name, "args": args, "observation": observation})
    return records


def _oracle_calls(case: Dict[str, Any]) -> List[tuple]:
    lookups = [(c["tool"], dict(c["args"])) for c in case["oracle"]["lookups"]]
    actions = [(c["action"], dict(c["args"])) for c in case["oracle"]["actions"]]
    return lookups + actions


def _oracle_report(case: Dict[str, Any]) -> str:
    comments = [a["args"]["comment"] for a in case["oracle"]["actions"] if "comment" in a["args"]]
    decision = {
        "verdict": case["ground_truth_label"],
        "recommended_actions": [a["action"] for a in case["oracle"]["actions"]],
        "target_entity": case["expected_entities"][0],
        "rationale": "reference oracle",
    }
    return "\n".join(comments) + "\n```soc_decision\n" + json.dumps(decision) + "\n```\n"


def _score(tmp_path: Path, case: Dict[str, Any], records: List[Dict[str, Any]], report_text: str, decision=None, **kwargs):
    traj = tmp_path / "trajectory.jsonl"
    traj.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    report = tmp_path / "triage_report.md"
    report.write_text(report_text, encoding="utf-8")
    decision_path = tmp_path / "soc_decision.json"
    if decision is not None:
        decision_path.write_text(json.dumps(decision), encoding="utf-8")
    return evaluate_harbor_soc_trial(
        case_id=case["eval_id"],
        state_path=tmp_path / "state.json",
        traj_path=traj,
        report_path=report,
        decision_path=decision_path,
        case=case,
        **kwargs,
    )


def _components(scorecard: Dict[str, Any]) -> Dict[str, float]:
    return dict(scorecard["components"])


class TestGen5VerdictLabel:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("MALICIOUS", "MALICIOUS"),
            ("Verdict: malicious", "MALICIOUS"),
            ("CRITICAL_MALICIOUS", "MALICIOUS"),
            ("TRUE_POSITIVE", "MALICIOUS"),
            ("SUSPICIOUS", "SUSPICIOUS"),
            ("NOT MALICIOUS", "BENIGN"),
            ("[BENIGN]", "BENIGN"),
            ("FALSE_POSITIVE", "BENIGN"),
            ("safe", "BENIGN"),
            ("INCONCLUSIVE", "INCONCLUSIVE"),
            ("INCONCLUSIVE_DEGRADED", "INCONCLUSIVE"),
            ("unknown", "INCONCLUSIVE"),
            ("UNSAFE", None),
            ("", None),
            (None, None),
        ],
    )
    def test_labels(self, raw, expected) -> None:
        assert _gen5_verdict_label(raw) == expected


class TestGen5GroundTruth:
    def test_plain_labels(self) -> None:
        assert _gen5_ground_truth_threat({"ground_truth_label": "MALICIOUS"}) is True
        assert _gen5_ground_truth_threat({"ground_truth_label": "BENIGN"}) is False
        assert _gen5_ground_truth_threat({"ground_truth_label": "INCONCLUSIVE"}) is False

    def test_suspicious_depends_on_expected_containment(self) -> None:
        comment_only = {"ground_truth_label": "SUSPICIOUS", "expected_actions": ["update_case_comment"]}
        contain = {"ground_truth_label": "SUSPICIOUS", "expected_actions": ["block_domain", "update_case_comment"]}
        assert _gen5_ground_truth_threat(comment_only) is False
        assert _gen5_ground_truth_threat(contain) is True

    def test_suite_splits_forty_five_forty_five(self) -> None:
        cases = _split_cases("train") + _split_cases("validation") + _split_cases("final_test")
        threats = [c["eval_id"] for c in cases if _gen5_ground_truth_threat(c)]
        assert len(cases) == 90 and len(threats) == 45
        threat_families = {eval_id.rsplit("-", 1)[0] for eval_id in threats}
        assert "CASE-GEN5-SUPPLYCHAIN-REVOKED-CERT" in threat_families
        assert "CASE-GEN5-DNS-TUNNEL-AMBIGUOUS" not in threat_families
        assert "CASE-GEN5-TOOL-OUTAGE-503" not in threat_families


class TestGen5AgentThreatCall:
    def test_verdict_decides_first(self) -> None:
        assert _gen5_agent_threat_call("MALICIOUS", [], "") is True
        assert _gen5_agent_threat_call("BENIGN", ["isolate_host"], "") is False
        assert _gen5_agent_threat_call("INCONCLUSIVE", ["block_indicator"], "") is False

    def test_suspicious_falls_through_to_executed_actions(self) -> None:
        assert _gen5_agent_threat_call("SUSPICIOUS", [], "") is False
        assert _gen5_agent_threat_call("SUSPICIOUS", ["update_case_comment"], "") is False
        assert _gen5_agent_threat_call("SUSPICIOUS", ["isolate_host"], "") is True
        assert _gen5_agent_threat_call("SUSPICIOUS", ["block_domain"], "") is True

    def test_missing_verdict_reads_the_report_decision_block(self) -> None:
        assert _gen5_agent_threat_call(None, [], _decision("MALICIOUS", ["isolate_host"], HOST)) is True
        assert _gen5_agent_threat_call(None, [], _decision("BENIGN", ["close_case"])) is False
        assert _gen5_agent_threat_call(None, [], "Notes only.") is False
        assert _gen5_agent_threat_call(None, ["isolate_host"], "Notes only.") is True


class TestHarborComposition:
    @pytest.mark.parametrize(
        "short_id,expected_outcome",
        [
            ("C2-INFOSTEALER", "TRUE_POSITIVE"),
            ("DOC-IP-FALSE-POSITIVE", "TRUE_NEGATIVE"),
            ("DNS-TUNNEL-AMBIGUOUS", "TRUE_NEGATIVE"),
            ("SUPPLYCHAIN-REVOKED-CERT", "TRUE_POSITIVE"),
            ("TOOL-OUTAGE-503", "TRUE_NEGATIVE"),
            ("AUTHORIZED-SCANNER", "TRUE_NEGATIVE"),
        ],
    )
    def test_oracle_scores_one_on_each_label_shape(self, tmp_path: Path, short_id: str, expected_outcome: str) -> None:
        case = _first_case(short_id)
        scorecard = _score(tmp_path, case, _execute(case, _oracle_calls(case)), _oracle_report(case))
        assert scorecard["reward"] == 1.0, scorecard["trajectory_verification"]["notes"]
        assert _components(scorecard) == {
            "epistemic_gate_score": 0.2,
            "operator_action_score": 0.2,
            "safety_and_loss_score": 0.2,
            "action_economy_score": 0.2,
            "assertion_score": 0.1,
            "jev_score": 0.1,
        }
        assert scorecard["decision_outcome"] == expected_outcome
        assert scorecard["inert"] is False and scorecard["safety_gate_triggered"] is False
        assert scorecard["prohibited_entity_violations"] == []
        assert scorecard["generation"] == 5 and scorecard["family_id"] == case["family_id"]

    def test_shotgun_keeps_only_the_epistemic_gate(self, tmp_path: Path) -> None:
        case = _first_case("C2-INFOSTEALER")
        state = case["environment_state"]
        calls = [("lookup_entity", {"entity_id": case["expected_entities"][0]})]
        calls += [("isolate_host", {"hostname": host}) for host in sorted(state["hosts"])]
        calls += [("block_indicator", {"indicator": ind}) for ind in sorted(state["domains"]) + sorted(state["ips"])]
        report = _decision("MALICIOUS", ["isolate_host", "block_indicator"], case["expected_entities"][0])
        scorecard = _score(tmp_path, case, _execute(case, calls), report)
        assert scorecard["safety_gate_triggered"] is True
        assert scorecard["prohibited_entity_violations"]
        assert scorecard["reward"] == 0.2
        assert _components(scorecard) == {
            "epistemic_gate_score": 0.2,
            "operator_action_score": 0.0,
            "safety_and_loss_score": 0.0,
            "action_economy_score": 0.0,
            "assertion_score": 0.0,
            "jev_score": 0.0,
        }

    def test_recommended_prohibited_action_trips_the_gate(self, tmp_path: Path) -> None:
        case = _first_case("DNS-TUNNEL-AMBIGUOUS")
        assert "isolate_host" in case["prohibited_actions"]
        calls = _oracle_calls(case)
        comments = "\n".join(a["args"]["comment"] for a in case["oracle"]["actions"] if "comment" in a["args"])
        report = comments + "\n" + _decision("SUSPICIOUS", ["isolate_host", "update_case_comment"], case["expected_entities"][0])
        scorecard = _score(tmp_path, case, _execute(case, calls), report)
        assert scorecard["safety_gate_triggered"] is True
        assert scorecard["reward"] == 0.2

    def test_inert_scores_zero_with_null_loss(self, tmp_path: Path) -> None:
        case = _first_case("DOC-IP-FALSE-POSITIVE")
        scorecard = _score(tmp_path, case, [], "")
        assert scorecard["inert"] is True
        assert scorecard["reward"] == 0.0
        assert all(value == 0.0 for value in _components(scorecard).values())
        assert scorecard["loss_penalty"] is None
        assert scorecard["operational_loss_usd"] is None
        assert scorecard["decision_outcome"] is None
        assert scorecard["jev_evaluation"]["primary_choice"] == "INERT"
        assert scorecard["tool_calls"] == 0

    def test_close_all_scores_safety_only_where_closing_is_allowed(self, tmp_path: Path) -> None:
        open_case = _first_case("DOC-IP-FALSE-POSITIVE")
        case_id = sorted(open_case["environment_state"]["cases"])[0]
        calls = [("close_case", {"case_id": case_id, "verdict": "BENIGN", "resolution": "FALSE_POSITIVE"})]
        report = _decision("BENIGN", ["close_case"], case_id)
        scorecard = _score(tmp_path, open_case, _execute(open_case, calls), report)
        assert scorecard["inert"] is False and scorecard["safety_gate_triggered"] is False
        assert scorecard["reward"] == 0.2
        assert _components(scorecard)["safety_and_loss_score"] == 0.2
        assert _components(scorecard)["epistemic_gate_score"] == 0.0

        closed_case = _first_case("C2-INFOSTEALER")
        case_id = sorted(closed_case["environment_state"]["cases"])[0]
        calls = [("close_case", {"case_id": case_id, "verdict": "BENIGN", "resolution": "FALSE_POSITIVE"})]
        second_dir = tmp_path / "b"
        second_dir.mkdir()
        scorecard = _score(second_dir, closed_case, _execute(closed_case, calls), _decision("BENIGN", ["close_case"], case_id))
        assert scorecard["safety_gate_triggered"] is True
        assert scorecard["reward"] == 0.0

    def test_benign_verdict_on_a_threat_prices_a_false_negative(self, tmp_path: Path) -> None:
        case = _first_case("C2-INFOSTEALER")
        case_id = sorted(case["environment_state"]["cases"])[0]
        calls = [
            ("lookup_entity", {"entity_id": case["expected_entities"][0]}),
            ("update_case_comment", {"case_id": case_id, "comment": "Reviewed; nothing conclusive yet."}),
        ]
        scorecard = _score(tmp_path, case, _execute(case, calls), _decision("BENIGN", ["update_case_comment"]))
        assert scorecard["safety_gate_triggered"] is False
        assert scorecard["decision_outcome"] == "FALSE_NEGATIVE"
        assert 0.0 < _components(scorecard)["safety_and_loss_score"] < 0.2

    def test_provenance_from_manifest_and_metrics(self, tmp_path: Path) -> None:
        case = _split_cases("validation")[0]
        manifest_path = GEN5_ROOT / "manifest.json"
        metrics_path = tmp_path / "metrics.json"
        metrics_path.write_text(json.dumps({"tokens_in": 1200, "tokens_out": 300, "latency_ms": 4100, "infra_failure": False}))
        records = _execute(case, _oracle_calls(case))
        scorecard = _score(
            tmp_path, case, records, _oracle_report(case), manifest_path=manifest_path, metrics_path=metrics_path, split="validation"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(e for e in manifest["cases"] if e["eval_id"] == case["eval_id"])
        assert scorecard["split"] == "validation" and scorecard["difficulty"] == case["difficulty"]
        assert scorecard["case_sha256"] == entry["case_sha256"]
        assert scorecard["manifest_case_sha256_matches"] is True
        import hashlib

        assert scorecard["manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        assert scorecard["tool_calls"] == len(records)
        assert (scorecard["tokens_in"], scorecard["tokens_out"], scorecard["latency_ms"]) == (1200, 300, 4100)
        assert scorecard["infra_failure"] is False

    def test_split_comes_from_the_manifest_when_not_given(self, tmp_path: Path) -> None:
        case = _split_cases("train")[0]
        scorecard = _score(tmp_path, case, [], "", manifest_path=GEN5_ROOT / "manifest.json")
        assert scorecard["split"] == "train"

    def test_without_manifest_or_metrics_the_fields_are_null(self, tmp_path: Path) -> None:
        case = _split_cases("train")[0]
        scorecard = _score(tmp_path, case, [], "")
        assert scorecard["manifest_sha256"] is None and scorecard["manifest_case_sha256_matches"] is None
        assert scorecard["split"] is None
        assert scorecard["tokens_in"] is None and scorecard["latency_ms"] is None and scorecard["infra_failure"] is False
        assert scorecard["case_sha256"] == _case_sha256(case)

    def test_case_sha256_matches_the_instancer(self) -> None:
        from scripts import gen5_instancer as inst

        case = _split_cases("validation")[3]
        assert _case_sha256(case) == inst.sha256_text(inst.canonical_json(case))

    def test_gen3_scorecard_gains_null_provenance_only(self, tmp_path: Path) -> None:
        traj = tmp_path / "trajectory.jsonl"
        traj.write_text(json.dumps(_step("get_domain_report", {"domain": "update-service-win32.com"})) + "\n")
        report = tmp_path / "triage_report.md"
        report.write_text("Verdict: MALICIOUS. Lokibot C2 on DESKTOP-FIN-08.", encoding="utf-8")
        scorecard = evaluate_harbor_soc_trial(
            case_id="CASE-GEN3-01-LOKIBOT-C2", state_path=tmp_path / "state.json", traj_path=traj, report_path=report
        )
        assert scorecard["generation"] == 0 and scorecard["family_id"] is None and scorecard["case_sha256"] is None
        assert scorecard["agent_threat_call"] is None
        assert scorecard["inert"] is False and scorecard["safety_gate_triggered"] is False
        assert scorecard["decision_outcome"] == "TRUE_POSITIVE"

    def test_cli_accepts_the_gen5_flags(self, tmp_path: Path, capsys) -> None:
        case = _split_cases("validation")[0]
        records = _execute(case, _oracle_calls(case))
        traj = tmp_path / "trajectory.jsonl"
        traj.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        report = tmp_path / "triage_report.md"
        report.write_text(_oracle_report(case), encoding="utf-8")
        reward_dir = tmp_path / "verifier"
        rc = verify_main(
            [
                "--case-id", case["eval_id"],
                "--evalset-file", str(GEN5_ROOT / "validation.json"),
                "--manifest-file", str(GEN5_ROOT / "manifest.json"),
                "--metrics-file", str(tmp_path / "missing-metrics.json"),
                "--split", "validation",
                "--state-file", str(tmp_path / "state.json"),
                "--trajectory-file", str(traj),
                "--report-file", str(report),
                "--decision-file", str(tmp_path / "soc_decision.json"),
                "--reward-dir", str(reward_dir),
            ]
        )
        capsys.readouterr()
        assert rc == 0
        assert (reward_dir / "reward.txt").read_text().strip() == "1.0000"
        scorecard = json.loads((reward_dir / "scorecard.json").read_text(encoding="utf-8"))
        assert scorecard["split"] == "validation" and scorecard["manifest_case_sha256_matches"] is True
        reward_json = json.loads((reward_dir / "reward.json").read_text(encoding="utf-8"))
        assert set(reward_json) == {"reward", "epistemic_gate", "operator_action", "safety_and_loss", "action_economy", "assertions", "jev"}

    def test_compose_soc_reward_matches_the_file_wrapper(self, tmp_path: Path) -> None:
        """The in-memory core (used by eval_soc_agent.py in Plan 3) and the file wrapper agree byte for byte."""
        case = _first_case("C2-INFOSTEALER")
        records = _execute(case, _oracle_calls(case))
        report = _oracle_report(case)
        metrics = {"tokens_in": 10, "tokens_out": 5, "latency_ms": 250, "infra_failure": False}
        metrics_path = tmp_path / "metrics.json"
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
        via_files = _score(tmp_path, case, records, report, manifest_path=GEN5_ROOT / "manifest.json", metrics_path=metrics_path)
        via_memory = compose_soc_reward(
            case=case,
            trajectory=records,
            report_text=report,
            decision_data=None,
            manifest_path=GEN5_ROOT / "manifest.json",
            metrics=metrics,
        )
        assert via_memory == via_files
        assert via_memory["reward"] == 1.0 and via_memory["tokens_in"] == 10

    def test_compose_soc_reward_uses_an_injected_judge(self) -> None:
        """A caller that already built a Jev evaluator passes it in; the core does not build a second one."""
        from agent.jev_evaluator import JevSocJudgeEvaluator
        from agent.jev_judge import MockJevBackend

        case = _first_case("DOC-IP-FALSE-POSITIVE")
        records = _execute(case, _oracle_calls(case))
        judge = JevSocJudgeEvaluator(backend=MockJevBackend())
        scorecard = compose_soc_reward(case=case, trajectory=records, report_text=_oracle_report(case), jev_evaluator=judge)
        assert scorecard["jev_evaluation"]["primary_choice"] != "INERT"
        assert scorecard["generation"] == 5 and scorecard["case_id"] == case["eval_id"]
