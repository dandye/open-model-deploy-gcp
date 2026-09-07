"""Exercise evaluator/optimizer/collector contracts without cloud or model calls."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent.gepa_runbook_optimizer import CORE_RUNBOOKS, RunbookGEPAAdapter
from agent.hierarchical_soc_agent import SOCTier1Response
from agent.soc_environment import SocEnvironment
from scripts.eval_soc_agent import SemanticJudgeResult, run_evaluation
from scripts.run_gce_spot_sweep import ALL_GCE_SPOT_TARGETS, GCESpotOrchestrator


@pytest.fixture
def pipeline(tmp_path):
    observations = []

    class ProbeAgent:
        def __init__(self, environment=None, **kwargs):
            self.environment = environment

        def set_up(self):
            pass

        def query(self, prompt, **kwargs):
            observation = self.environment.query_tool('get_domain_report', {'domain': 'evil.com'})
            observations.append(observation)
            return SOCTier1Response(
                response='INCONCLUSIVE', verdict='INCONCLUSIVE',
                trajectory=[{'tool': 'get_domain_report', 'args': {'domain': 'evil.com'},
                             'observation': json.dumps(observation)}],
            )

    cases = [
        {'eval_id': 'outage', 'name': 'Injected outage', 'prompt': 'Investigate evil.com',
         'ground_truth_label': 'INCONCLUSIVE', 'reference': {'grading_rubric': 'Report outage'},
         'fault_injection': {'tool': 'get_domain_report', 'status_code': 503, 'error': 'review outage'}},
        {'eval_id': 'normal', 'name': 'Normal lookup', 'prompt': 'Investigate evil.com',
         'ground_truth_label': 'MALICIOUS', 'reference': {'grading_rubric': 'Investigate evidence'}},
    ]
    path = tmp_path / 'cases.json'
    path.write_text(json.dumps({'generation': 3, 'eval_cases': cases}))
    judge = SemanticJudgeResult(rubric_score=90, passed=True, grounding_score=1, critique='offline fixture')
    with patch('scripts.eval_soc_agent.SocTier1Agent', ProbeAgent), \
         patch('scripts.eval_soc_agent.genai.Client'), \
         patch('scripts.eval_soc_agent.judge_response_with_llm', return_value=judge):
        result = run_evaluation(path, ALL_GCE_SPOT_TARGETS[0].flavor,
                                managed_model='offline-model', project_id='offline-project')
    return result, cases, ProbeAgent, observations


def test_optimizer_and_evaluator_apply_identical_faults_without_case_leakage(pipeline):
    _, cases, agent_factory, observations = pipeline
    evaluator_observations = list(observations)
    observations.clear()
    adapter = RunbookGEPAAdapter(project_id='offline-project', agent_factory=agent_factory)
    batch = adapter.evaluate(cases, {name: '# Investigate evidence' for name in CORE_RUNBOOKS})
    assert len(batch.scores) == 2
    assert observations == evaluator_observations
    assert observations[0]['status_code'] == 503
    assert observations[0]['error'] == 'review outage'
    assert 'status_code' not in observations[1]
    assert observations[1]['verdict'] == 'MALICIOUS'


def collect_artifact(tmp_path, artifact):
    def fake_copy(command, **kwargs):
        # The collector owns the output filename and creates its directory.
        destination = Path(command[-1])
        destination.write_text(json.dumps(artifact))
        return SimpleNamespace(returncode=0)

    collector = GCESpotOrchestrator(dry_run=False, output_gcs_bucket='gs://offline-fixture')
    with patch('scripts.run_gce_spot_sweep.subprocess.run', side_effect=fake_copy):
        return collector.collect_results(ALL_GCE_SPOT_TARGETS[0], output_dir=tmp_path)


def test_actual_evaluator_result_round_trips_through_collector(pipeline, tmp_path):
    result, _, _, _ = pipeline
    assert result['status'] == 'COMPLETED'
    assert result['provenance']['lifecycle']['evaluation'] == 'completed'
    collected = collect_artifact(tmp_path, result)
    assert collected['status'] == 'COMPLETED'
    assert collected['case_results'] == result['case_results']
    assert collected['artifact_collection']['status'] == 'COLLECTED'
    assert collected['artifact_collection']['run_identity_verified'] is False


@pytest.mark.parametrize('signals,expected', [
    ({'provenance': {'lifecycle': {'evaluation': 'completed', 'cleanup': 'unverified'}}}, 'COMPLETED'),
    ({'status': 'COMPLETED', 'provenance': {'lifecycle': {'evaluation': 'failed'}}}, 'FAILED'),
    ({'status': 'FAILED', 'provenance': {'lifecycle': {'evaluation': 'completed'}}}, 'FAILED'),
    ({'evaluation': {'status': 'ERROR'}}, 'ERROR'),
    ({'evaluation': {'status': 'COMPLETED', 'evaluator_exit_status': 7}}, 'FAILED'),
    ({'status': 'COMPLETED', 'provenance': {'lifecycle': {'evaluation': 'running'}}}, 'UNVERIFIED'),
    ({'summary': {'pass_rate': 100}}, 'UNVERIFIED'),
])
def test_collector_uses_evaluation_signals_without_claiming_cleanup(tmp_path, signals, expected):
    collected = collect_artifact(tmp_path, signals)
    assert collected['status'] == expected
    assert collected['artifact_collection']['run_identity_verified'] is False


@pytest.mark.parametrize('fault', [{}, {'tool': ''}, 'get_domain_report'])
def test_malformed_declared_fault_is_not_silently_ignored(fault):
    with pytest.raises(ValueError, match='fault_injection'):
        SocEnvironment.from_eval_case({'fault_injection': fault})


def test_fault_defaults_and_normal_case_state_are_independent():
    faulty = SocEnvironment.from_eval_case({'fault_injection': {'tool': 'get_domain_report'}})
    normal = SocEnvironment.from_eval_case({})
    assert faulty.query_tool('get_domain_report', {'domain': 'evil.com'})['status_code'] == 503
    assert normal.faults == {}


def test_gepa_live_mode_does_not_install_simulated_faults():
    environments = []

    def factory(**kwargs):
        environments.append(kwargs['environment'])
        return SimpleNamespace(query=lambda *args, **kw: SOCTier1Response(response='INCONCLUSIVE'))

    adapter = RunbookGEPAAdapter(project_id='offline-project', use_live_mcp=True, agent_factory=factory)
    adapter.evaluate([{'prompt': 'Investigate', 'fault_injection': {'tool': 'get_domain_report'}}],
                     {name: '# Investigate evidence' for name in CORE_RUNBOOKS})
    assert environments == [None]
