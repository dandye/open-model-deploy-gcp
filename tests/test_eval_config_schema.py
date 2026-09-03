"""Unit and schema validation tests for expanded 10-case SOC Tier 1 evaluation suite."""

import json
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "configs" / "evals" / "soc_tier1_triage.json"

EXPECTED_CASE_IDS = [
    "CASE-01-LOKIBOT-C2",
    "CASE-02-RFC5737-BENIGN-IP",
    "CASE-03-PHISHING-CRED-HARVEST",
    "CASE-04-DUPLICATE-SOAR-CASE",
    "CASE-05-RANSOMWARE-ESCALATION",
    "CASE-06-AMBIGUOUS-DNS-TUNNEL",
    "CASE-07-LATERAL-MOVEMENT",
    "CASE-08-SUPPLY-CHAIN-REVOKED-CERT",
    "CASE-09-TOOL-FAILURE-RESILIENCE",
    "CASE-10-AUTHORIZED-SCANNER-TRUE-NEGATIVE",
]


def test_eval_suite_contains_ten_cases():
    """Verify configs/evals/soc_tier1_triage.json contains exactly 10 valid cases."""
    assert CONFIG_PATH.exists(), f"Expected eval config file at {CONFIG_PATH}"
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert data.get("evalset_id") == "soc_tier1_triage"
    assert isinstance(data.get("name"), str) and len(data["name"]) > 0
    assert isinstance(data.get("description"), str) and len(data["description"]) > 0
    assert isinstance(data.get("eval_cases"), list)
    assert len(data["eval_cases"]) == 10

    case_ids = [c.get("eval_id") for c in data["eval_cases"]]
    assert case_ids == EXPECTED_CASE_IDS


def test_eval_suite_case_structure_and_types():
    """Verify all 10 cases have required schema fields, rubric, and assertions."""
    assert CONFIG_PATH.exists()
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    for case in data.get("eval_cases", []):
        eval_id = case.get("eval_id", "<unknown>")
        assert "eval_id" in case, "Case missing eval_id"
        assert isinstance(case.get("name"), str) and len(case["name"]) > 0, f"{eval_id}: missing name"
        assert isinstance(case.get("prompt"), str) and len(case["prompt"]) > 0, f"{eval_id}: missing prompt"

        # Reference validation
        ref = case.get("reference")
        assert isinstance(ref, dict), f"{eval_id}: reference must be a dict"
        assert "expected_verdict" in ref, f"{eval_id}: reference missing expected_verdict"
        assert "grading_rubric" in ref, f"{eval_id}: reference missing grading_rubric"
        assert isinstance(ref["grading_rubric"], str) and len(ref["grading_rubric"]) > 0

        # Assertions validation
        assertions = case.get("assertions")
        assert isinstance(assertions, dict), f"{eval_id}: assertions must be a dict"
        assert "must_contain" in assertions, f"{eval_id}: assertions missing must_contain"
        assert "must_not_contain" in assertions, f"{eval_id}: assertions missing must_not_contain"
        assert isinstance(assertions["must_contain"], list), f"{eval_id}: must_contain must be list"
        assert isinstance(assertions["must_not_contain"], list), f"{eval_id}: must_not_contain must be list"
        assert len(assertions["must_contain"]) > 0, f"{eval_id}: must_contain must be non-empty"


def test_eval_suite_no_emojis():
    """Verify zero unicode emojis exist in soc_tier1_triage.json."""
    assert CONFIG_PATH.exists()
    raw_text = CONFIG_PATH.read_text(encoding="utf-8")

    for char in raw_text:
        cp = ord(char)
        is_emoji = (
            (0x1F600 <= cp <= 0x1F64F)
            or (0x1F300 <= cp <= 0x1F5FF)
            or (0x1F680 <= cp <= 0x1F6FF)
            or (0x1F700 <= cp <= 0x1F77F)
            or (0x1F780 <= cp <= 0x1F7FF)
            or (0x1F800 <= cp <= 0x1F8FF)
            or (0x1F900 <= cp <= 0x1F9FF)
            or (0x1FA00 <= cp <= 0x1FA6F)
            or (0x1FA70 <= cp <= 0x1FAFF)
            or (0x2600 <= cp <= 0x26FF)
            or (0x2700 <= cp <= 0x27BF)
        )
        assert not is_emoji, f"Emoji character detected in eval config: '{char}' (U+{cp:04X})"


EXPECTED_LIVE_CASE_IDS = [
    "CASE-LIVE-01-ENCODED-POWERSHELL",
    "CASE-LIVE-02-COBALT-STRIKE-NAMEDPIPE",
    "CASE-LIVE-03-SCOUTSUITE-RECON",
    "CASE-LIVE-04-BIGQUERY-EXFIL",
    "CASE-LIVE-05-ACTIVE-QUEUE-TRIAGE",
    "CASE-LIVE-06-LOG-CLEARING-DEFENSE-EVASION",
    "CASE-LIVE-07-ATERA-RMM-TOOL-CALLBACK",
    "CASE-LIVE-08-POWERSHELL-IEX-OBFUSCATION",
    "CASE-LIVE-09-OFFENSIVE-SECURITY-DISTRO",
    "CASE-LIVE-10-APPDATA-ALPHANUMERIC-BINARY",
]


def test_live_mcp_evalset_structure():
    """Verify configs/evals/soc_live_mcp_evalset.json has valid schema and 10 cases."""
    live_path = ROOT_DIR / "configs" / "evals" / "soc_live_mcp_evalset.json"
    assert live_path.exists(), f"Missing live MCP evalset at {live_path}"
    data = json.loads(live_path.read_text(encoding="utf-8"))
    assert data.get("evalset_id") == "soc_live_mcp_evalset"
    assert len(data.get("eval_cases", [])) == 10

    case_ids = [c.get("eval_id") for c in data["eval_cases"]]
    assert case_ids == EXPECTED_LIVE_CASE_IDS

    for case in data["eval_cases"]:
        eval_id = case.get("eval_id", "<unknown>")
        assert "eval_id" in case, "Live case missing eval_id"
        assert "prompt" in case, f"{eval_id}: missing prompt"
        assert "reference" in case, f"{eval_id}: missing reference"
        assert "grading_rubric" in case["reference"], f"{eval_id}: missing grading rubric"
        assert "assertions" in case, f"{eval_id}: missing assertions"
        assert len(case["assertions"].get("must_contain", [])) > 0, f"{eval_id}: must_contain empty"


def test_live_mcp_evalset_no_emojis():
    """Verify zero unicode emojis exist in soc_live_mcp_evalset.json."""
    live_path = ROOT_DIR / "configs" / "evals" / "soc_live_mcp_evalset.json"
    raw_text = live_path.read_text(encoding="utf-8")
    for char in raw_text:
        cp = ord(char)
        is_emoji = (
            (0x1F600 <= cp <= 0x1F64F)
            or (0x1F300 <= cp <= 0x1F5FF)
            or (0x1F680 <= cp <= 0x1F6FF)
            or (0x1F700 <= cp <= 0x1F77F)
            or (0x1F780 <= cp <= 0x1F7FF)
            or (0x1F800 <= cp <= 0x1F8FF)
            or (0x1F900 <= cp <= 0x1F9FF)
            or (0x1FA00 <= cp <= 0x1FA6F)
            or (0x1FA70 <= cp <= 0x1FAFF)
            or (0x2600 <= cp <= 0x26FF)
            or (0x2700 <= cp <= 0x27BF)
        )
        assert not is_emoji, f"Emoji character detected in live eval config: '{char}' (U+{cp:04X})"


GEN3_TIER1_PATH = ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json"
GEN3_LIVE_MCP_PATH = ROOT_DIR / "configs" / "evals" / "gen3" / "soc_live_mcp_interactive.json"

EXPECTED_GEN3_TIER1_CASE_IDS = [
    "CASE-GEN3-01-LOKIBOT-C2",
    "CASE-GEN3-02-RFC5737-BENIGN-IP",
    "CASE-GEN3-03-PHISHING-CRED-HARVEST",
    "CASE-GEN3-04-DUPLICATE-SOAR-CASE",
    "CASE-GEN3-05-RANSOMWARE-ESCALATION",
    "CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL",
    "CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC",
    "CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT",
    "CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE",
    "CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE",
]

EXPECTED_GEN3_TIER1_ASSERTIONS = {
    "CASE-GEN3-01-LOKIBOT-C2": {
        "must_contain": ["update-service-win32.com", "DESKTOP-FIN-08"],
        "must_not_contain": ["False Positive", "confirmed benign"],
    },
    "CASE-GEN3-02-RFC5737-BENIGN-IP": {
        "must_contain": ["192.0.2.100"],
        "must_not_contain": ["CRITICAL MALWARE", "Lokibot", "APT29"],
    },
    "CASE-GEN3-03-PHISHING-CRED-HARVEST": {
        "must_contain": ["john.doe", "evil.com"],
        "must_not_contain": ["BENIGN / SAFE", "False Positive"],
    },
    "CASE-GEN3-04-DUPLICATE-SOAR-CASE": {
        "must_contain": ["33279"],
        "must_not_contain": ["no existing cases"],
    },
    "CASE-GEN3-05-RANSOMWARE-ESCALATION": {
        "must_contain": ["DESKTOP-FIN-08", "10.0.5.23"],
        "must_not_contain": ["BENIGN / SAFE", "False Positive"],
    },
    "CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL": {
        "must_contain": ["tunnel-data.cdn-edge-update.net", "DESKTOP-FIN-08"],
        "must_not_contain": ["BENIGN / SAFE", "CONFIRMED CLEAN"],
    },
    "CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC": {
        "must_contain": ["DESKTOP-HR-04", "10.0.8.99"],
        "must_not_contain": ["BENIGN / SAFE", "False Positive"],
    },
    "CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT": {
        "must_contain": ["a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90", "invoice_update.exe"],
        "must_not_contain": ["VALID_CERTIFICATE", "clean software"],
    },
    "CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE": {
        "must_contain": ["error-503.service-unavailable.org", "503"],
        "must_not_contain": ["BENIGN / CONFIRMED SAFE", "CRITICAL MALWARE CONFIRMED"],
    },
    "CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE": {
        "must_contain": ["SRV-PROD-PAYMENT-01", "10.0.99.50"],
        "must_not_contain": ["CRITICAL MALWARE ATTACK", "isolate payment server"],
    },
}

EXPECTED_GEN3_LIVE_CASE_IDS = [
    "CASE-LIVE-01-ENCODED-POWERSHELL",
    "CASE-LIVE-02-COBALT-STRIKE-NAMEDPIPE",
    "CASE-LIVE-03-SCOUTSUITE-RECON",
    "CASE-LIVE-04-BIGQUERY-EXFIL",
    "CASE-LIVE-05-ACTIVE-QUEUE-TRIAGE",
    "CASE-LIVE-06-LOG-CLEARING-DEFENSE-EVASION",
    "CASE-LIVE-07-ATERA-RMM-TOOL-CALLBACK",
    "CASE-LIVE-08-POWERSHELL-IEX-OBFUSCATION",
    "CASE-LIVE-09-OFFENSIVE-SECURITY-DISTRO",
    "CASE-LIVE-10-APPDATA-ALPHANUMERIC-BINARY",
]

VALID_CRITICALITY_TIERS = {"LOW", "STANDARD", "HIGH", "CRITICAL"}
VALID_GROUND_TRUTH_LABELS = {"MALICIOUS", "BENIGN", "SUSPICIOUS", "INCONCLUSIVE"}


def test_gen3_tier1_interactive_structure():
    """Verify configs/evals/gen3/soc_tier1_interactive.json has valid Gen 3 schema and 10 cases."""
    assert GEN3_TIER1_PATH.exists(), f"Expected Gen 3 eval config at {GEN3_TIER1_PATH}"
    data = json.loads(GEN3_TIER1_PATH.read_text(encoding="utf-8"))

    assert data.get("evalset_id") == "soc_tier1_interactive"
    assert data.get("generation") == 3
    assert isinstance(data.get("name"), str) and len(data["name"]) > 0
    assert isinstance(data.get("description"), str) and len(data["description"]) > 0
    assert isinstance(data.get("eval_cases"), list)
    assert len(data["eval_cases"]) == 10

    case_ids = [c.get("eval_id") for c in data["eval_cases"]]
    assert case_ids == EXPECTED_GEN3_TIER1_CASE_IDS

    criticality_tiers_seen = set()
    labels_seen = set()

    for case in data["eval_cases"]:
        eval_id = case.get("eval_id", "<unknown>")
        assert "eval_id" in case, "Case missing eval_id"
        assert isinstance(case.get("name"), str) and len(case["name"]) > 0, f"{eval_id}: missing name"
        assert isinstance(case.get("prompt"), str) and len(case["prompt"]) > 0, f"{eval_id}: missing prompt"

        # Asset criticality and ground truth labels
        crit = case.get("asset_criticality")
        assert crit in VALID_CRITICALITY_TIERS, f"{eval_id}: invalid asset_criticality '{crit}'"
        criticality_tiers_seen.add(crit)

        gt_label = case.get("ground_truth_label")
        assert gt_label in VALID_GROUND_TRUTH_LABELS, f"{eval_id}: invalid ground_truth_label '{gt_label}'"
        labels_seen.add(gt_label)

        # Expected and prohibited actions
        assert isinstance(case.get("expected_actions"), list), f"{eval_id}: expected_actions must be list"
        assert isinstance(case.get("prohibited_actions"), list), f"{eval_id}: prohibited_actions must be list"
        assert isinstance(case.get("expected_entities"), list), f"{eval_id}: expected_entities must be list"

        # Reference validation
        ref = case.get("reference")
        assert isinstance(ref, dict), f"{eval_id}: reference must be a dict"
        assert "expected_verdict" in ref, f"{eval_id}: reference missing expected_verdict"
        assert isinstance(ref.get("grading_rubric"), str) and len(ref["grading_rubric"]) > 0

        # Assertions validation
        assertions = case.get("assertions")
        assert isinstance(assertions, dict), f"{eval_id}: assertions must be a dict"
        assert "must_contain" in assertions, f"{eval_id}: assertions missing must_contain"
        assert "must_not_contain" in assertions, f"{eval_id}: assertions missing must_not_contain"
        assert isinstance(assertions["must_contain"], list) and len(assertions["must_contain"]) > 0
        assert isinstance(assertions["must_not_contain"], list)

    assert criticality_tiers_seen == VALID_CRITICALITY_TIERS, "All 4 criticality tiers must be represented"


def test_gen3_tier1_interactive_no_emojis():
    """Verify zero unicode emojis exist in soc_tier1_interactive.json."""
    assert GEN3_TIER1_PATH.exists()
    raw_text = GEN3_TIER1_PATH.read_text(encoding="utf-8")
    for char in raw_text:
        cp = ord(char)
        is_emoji = (
            (0x1F600 <= cp <= 0x1F64F)
            or (0x1F300 <= cp <= 0x1F5FF)
            or (0x1F680 <= cp <= 0x1F6FF)
            or (0x1F700 <= cp <= 0x1F77F)
            or (0x1F780 <= cp <= 0x1F7FF)
            or (0x1F800 <= cp <= 0x1F8FF)
            or (0x1F900 <= cp <= 0x1F9FF)
            or (0x1FA00 <= cp <= 0x1FA6F)
            or (0x1FA70 <= cp <= 0x1FAFF)
            or (0x2600 <= cp <= 0x26FF)
            or (0x2700 <= cp <= 0x27BF)
        )
        assert not is_emoji, f"Emoji character detected in Gen 3 eval config: '{char}' (U+{cp:04X})"


def test_gen3_live_mcp_interactive_structure():
    """Verify configs/evals/gen3/soc_live_mcp_interactive.json has valid Gen 3 schema and 10 cases."""
    assert GEN3_LIVE_MCP_PATH.exists(), f"Expected Gen 3 Live MCP config at {GEN3_LIVE_MCP_PATH}"
    data = json.loads(GEN3_LIVE_MCP_PATH.read_text(encoding="utf-8"))

    assert data.get("evalset_id") == "soc_live_mcp_interactive"
    assert data.get("generation") == 3
    assert isinstance(data.get("name"), str) and len(data["name"]) > 0
    assert isinstance(data.get("description"), str) and len(data["description"]) > 0
    assert isinstance(data.get("eval_cases"), list)
    assert len(data["eval_cases"]) == 10

    case_ids = [c.get("eval_id") for c in data["eval_cases"]]
    assert case_ids == EXPECTED_GEN3_LIVE_CASE_IDS

    criticality_tiers_seen = set()

    for case in data["eval_cases"]:
        eval_id = case.get("eval_id", "<unknown>")
        assert "eval_id" in case, "Live case missing eval_id"
        assert isinstance(case.get("name"), str) and len(case["name"]) > 0, f"{eval_id}: missing name"
        assert isinstance(case.get("prompt"), str) and len(case["prompt"]) > 0, f"{eval_id}: missing prompt"

        crit = case.get("asset_criticality")
        assert crit in VALID_CRITICALITY_TIERS, f"{eval_id}: invalid asset_criticality '{crit}'"
        criticality_tiers_seen.add(crit)

        gt_label = case.get("ground_truth_label")
        assert gt_label in VALID_GROUND_TRUTH_LABELS, f"{eval_id}: invalid ground_truth_label '{gt_label}'"

        assert isinstance(case.get("expected_actions"), list), f"{eval_id}: expected_actions must be list"
        assert isinstance(case.get("prohibited_actions"), list), f"{eval_id}: prohibited_actions must be list"
        assert isinstance(case.get("expected_entities"), list), f"{eval_id}: expected_entities must be list"

        ref = case.get("reference")
        assert isinstance(ref, dict), f"{eval_id}: reference must be a dict"
        assert isinstance(ref.get("grading_rubric"), str) and len(ref["grading_rubric"]) > 0

        assertions = case.get("assertions")
        assert isinstance(assertions, dict), f"{eval_id}: assertions must be a dict"
        assert "must_contain" in assertions, f"{eval_id}: assertions missing must_contain"
        assert "must_not_contain" in assertions, f"{eval_id}: assertions missing must_not_contain"
        assert isinstance(assertions["must_contain"], list) and len(assertions["must_contain"]) > 0
        assert isinstance(assertions["must_not_contain"], list)

    assert len(criticality_tiers_seen) >= 3, "Multiple criticality tiers must be represented"


def test_gen3_live_mcp_interactive_no_emojis():
    """Verify zero unicode emojis exist in soc_live_mcp_interactive.json."""
    assert GEN3_LIVE_MCP_PATH.exists()
    raw_text = GEN3_LIVE_MCP_PATH.read_text(encoding="utf-8")
    for char in raw_text:
        cp = ord(char)
        is_emoji = (
            (0x1F600 <= cp <= 0x1F64F)
            or (0x1F300 <= cp <= 0x1F5FF)
            or (0x1F680 <= cp <= 0x1F6FF)
            or (0x1F700 <= cp <= 0x1F77F)
            or (0x1F780 <= cp <= 0x1F7FF)
            or (0x1F800 <= cp <= 0x1F8FF)
            or (0x1F900 <= cp <= 0x1F9FF)
            or (0x1FA00 <= cp <= 0x1FA6F)
            or (0x1FA70 <= cp <= 0x1FAFF)
            or (0x2600 <= cp <= 0x26FF)
            or (0x2700 <= cp <= 0x27BF)
        )
        assert not is_emoji, f"Emoji character detected in Gen 3 live config: '{char}' (U+{cp:04X})"


def test_gen3_tier1_sanitized_assertions():
    """Verify Gen 3 interactive dataset assertions match sanitized specification."""
    assert GEN3_TIER1_PATH.exists()
    data = json.loads(GEN3_TIER1_PATH.read_text(encoding="utf-8"))

    assert len(data["eval_cases"]) == len(EXPECTED_GEN3_TIER1_ASSERTIONS)

    for case in data["eval_cases"]:
        eval_id = case["eval_id"]
        assert eval_id in EXPECTED_GEN3_TIER1_ASSERTIONS, f"Unexpected or missing case: {eval_id}"
        expected = EXPECTED_GEN3_TIER1_ASSERTIONS[eval_id]
        actual_mc = case["assertions"]["must_contain"]
        actual_mnc = case["assertions"]["must_not_contain"]

        assert actual_mc == expected["must_contain"], f"{eval_id}: must_contain mismatch"
        assert actual_mnc == expected["must_not_contain"], f"{eval_id}: must_not_contain mismatch"

        # Explicitly verify no brittle substrings
        assert "escalat" not in actual_mc, f"{eval_id}: brittle substring 'escalat' present"
        assert "Qualys" not in actual_mc, f"{eval_id}: brittle substring 'Qualys' present"
        assert "BENIGN" not in actual_mnc, f"{eval_id}: raw 'BENIGN' present in must_not_contain"


def test_gen3_live_mcp_sanitized_assertions():
    """Verify Gen 3 live MCP interactive assertions are sanitized and avoid raw BENIGN."""
    assert GEN3_LIVE_MCP_PATH.exists()
    data = json.loads(GEN3_LIVE_MCP_PATH.read_text(encoding="utf-8"))

    for case in data["eval_cases"]:
        eval_id = case["eval_id"]
        actual_mc = case["assertions"]["must_contain"]
        actual_mnc = case["assertions"]["must_not_contain"]

        assert len(actual_mc) > 0, f"{eval_id}: empty must_contain"
        assert len(actual_mnc) > 0, f"{eval_id}: empty must_not_contain"

        # Explicitly verify no brittle substrings
        assert "escalat" not in actual_mc, f"{eval_id}: brittle substring 'escalat' present"
        assert "BENIGN" not in actual_mnc, f"{eval_id}: raw 'BENIGN' present in must_not_contain"


def test_gen3_tier1_cmdb_asset_context():
    """Verify explicit CMDB asset owner, role, and blast radius in all 10 Gen 3 case prompts."""
    assert GEN3_TIER1_PATH.exists()
    data = json.loads(GEN3_TIER1_PATH.read_text(encoding="utf-8"))

    cases = data.get("eval_cases", [])
    assert len(cases) == 10

    for case in cases:
        eval_id = case.get("eval_id", "<unknown>")
        prompt = case.get("prompt", "")

        # Verify CMDB context block in prompt text
        assert "CMDB Asset Context" in prompt, f"{eval_id}: prompt missing CMDB Asset Context header"

        # Verify structured cmdb_context dictionary
        cmdb = case.get("cmdb_context")
        assert isinstance(cmdb, dict), f"{eval_id}: missing or invalid cmdb_context dict"
        assert isinstance(cmdb.get("asset_id"), str) and len(cmdb["asset_id"]) > 0, f"{eval_id}: missing asset_id"
        assert isinstance(cmdb.get("owner"), str) and len(cmdb["owner"]) > 0, f"{eval_id}: missing owner"
        assert isinstance(cmdb.get("business_role"), str) and len(cmdb["business_role"]) > 0, f"{eval_id}: missing business_role"
        assert isinstance(cmdb.get("blast_radius"), str) and len(cmdb["blast_radius"]) > 0, f"{eval_id}: missing blast_radius"


def test_gen3_tier1_cmdb_case_specific_details():
    """Verify case-specific CMDB roles, owners, and blast radius criteria across all 10 cases."""
    assert GEN3_TIER1_PATH.exists()
    data = json.loads(GEN3_TIER1_PATH.read_text(encoding="utf-8"))
    cases_by_id = {c["eval_id"]: c for c in data["eval_cases"]}

    # Case 1: Standard financial workstation (J. Smith), standard containment protocol
    c1_prompt = cases_by_id["CASE-GEN3-01-LOKIBOT-C2"]["prompt"]
    assert "Standard financial workstation" in c1_prompt
    assert "J. Smith" in c1_prompt
    assert "standard containment protocol" in c1_prompt.lower()

    # Case 2: Core VPN Gateway, connection attempts from IP 192.0.2.100 (unspoiled)
    c2_prompt = cases_by_id["CASE-GEN3-02-RFC5737-BENIGN-IP"]["prompt"]
    assert "Core VPN Gateway" in c2_prompt
    assert "192.0.2.100" in c2_prompt

    # Case 3: Standard marketing workstation (John Doe), phishing credential harvesting alert
    c3_prompt = cases_by_id["CASE-GEN3-03-PHISHING-CRED-HARVEST"]["prompt"]
    assert "Standard marketing workstation" in c3_prompt
    assert "John Doe" in c3_prompt
    assert "phishing credential harvesting" in c3_prompt.lower()

    # Case 4: Standard workstation, prior SOAR case correlation (CASE-33279)
    c4_prompt = cases_by_id["CASE-GEN3-04-DUPLICATE-SOAR-CASE"]["prompt"]
    assert "Standard workstation" in c4_prompt
    assert "CASE-33279" in c4_prompt

    # Case 5: Critical financial controller asset (DESKTOP-FIN-08), active ransomware, immediate isolation required ($250k FN breach risk), do NOT reboot host
    c5_prompt = cases_by_id["CASE-GEN3-05-RANSOMWARE-ESCALATION"]["prompt"]
    assert "DESKTOP-FIN-08" in c5_prompt
    assert "Critical financial controller asset" in c5_prompt
    assert "active ransomware" in c5_prompt.lower()
    assert "$250k" in c5_prompt or "250,000" in c5_prompt
    assert "do NOT reboot host" in c5_prompt

    # Case 6: Critical CFO workstation (Sarah Jenkins) during quarterly earnings close. Explicit warning: Unauthorized isolation incurs $50k FP downtime disruption; do NOT isolate without confirmed malicious C2 evidence
    c6_prompt = cases_by_id["CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL"]["prompt"]
    assert "Critical CFO workstation" in c6_prompt
    assert "Sarah Jenkins" in c6_prompt
    assert "quarterly earnings close" in c6_prompt
    assert "$50k" in c6_prompt or "50,000" in c6_prompt
    assert "do NOT isolate without confirmed malicious C2 evidence" in c6_prompt

    # Case 7: High-criticality HR asset (DESKTOP-HR-04) storing employee PII, PsExec lateral movement ($50k risk)
    c7_prompt = cases_by_id["CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC"]["prompt"]
    assert "DESKTOP-HR-04" in c7_prompt
    assert "employee PII" in c7_prompt
    assert "PsExec" in c7_prompt
    assert "$50k" in c7_prompt or "50,000" in c7_prompt

    # Case 8: Supply chain binary (invoice_update.exe), enterprise deployment pipeline (unspoiled)
    c8_prompt = cases_by_id["CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT"]["prompt"]
    assert "invoice_update.exe" in c8_prompt
    assert "Enterprise Software Deployment Pipeline" in c8_prompt

    # Case 9: Upstream 503 intelligence outage, degraded mode, do NOT close or isolate without verified evidence
    c9_prompt = cases_by_id["CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE"]["prompt"]
    assert "503" in c9_prompt
    assert "degraded mode" in c9_prompt.lower()
    assert "do NOT close or isolate without verified evidence" in c9_prompt

    # Case 10: Critical production payment server (SRV-PROD-PAYMENT-01), port scanning from internal subnet (unspoiled)
    c10_prompt = cases_by_id["CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE"]["prompt"]
    assert "SRV-PROD-PAYMENT-01" in c10_prompt
    assert "$50k" in c10_prompt or "50,000" in c10_prompt
    assert "Payment Infrastructure Engineering" in c10_prompt


def test_gen3_tier1_counterfactual_pairing():
    """Verify counterfactual pairing identifiers and symmetric configuration in Gen 3 suite."""
    assert GEN3_TIER1_PATH.exists()
    data = json.loads(GEN3_TIER1_PATH.read_text(encoding="utf-8"))
    cases = data.get("eval_cases", [])
    assert len(cases) == 10

    # Ensure counterfactual_pair_id is explicitly defined on each case
    for case in cases:
        eval_id = case.get("eval_id", "<unknown>")
        assert "counterfactual_pair_id" in case, f"{eval_id}: missing counterfactual_pair_id attribute"

    cases_by_id = {c["eval_id"]: c for c in cases}

    # Verify PAIR-01 (Case 1 & Case 6)
    c1 = cases_by_id["CASE-GEN3-01-LOKIBOT-C2"]
    c6 = cases_by_id["CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL"]
    assert c1["counterfactual_pair_id"] == "PAIR-01"
    assert c6["counterfactual_pair_id"] == "PAIR-01"
    assert c1["ground_truth_label"] == "MALICIOUS"
    assert c6["ground_truth_label"] == "SUSPICIOUS"
    assert "isolate_host" in c1["expected_actions"]
    assert "isolate_host" in c6["prohibited_actions"]

    # Verify PAIR-02 (Case 5 & Case 10)
    c5 = cases_by_id["CASE-GEN3-05-RANSOMWARE-ESCALATION"]
    c10 = cases_by_id["CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE"]
    assert c5["counterfactual_pair_id"] == "PAIR-02"
    assert c10["counterfactual_pair_id"] == "PAIR-02"
    assert c5["ground_truth_label"] == "MALICIOUS"
    assert c10["ground_truth_label"] == "BENIGN"
    assert "isolate_host" in c5["expected_actions"]
    assert "isolate_host" in c10["prohibited_actions"]

    # Verify unpaired cases have null / None counterfactual_pair_id
    unpaired_ids = [
        "CASE-GEN3-02-RFC5737-BENIGN-IP",
        "CASE-GEN3-03-PHISHING-CRED-HARVEST",
        "CASE-GEN3-04-DUPLICATE-SOAR-CASE",
        "CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC",
        "CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT",
        "CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE",
    ]
    for cid in unpaired_ids:
        assert cases_by_id[cid]["counterfactual_pair_id"] is None, f"{cid} should have null counterfactual_pair_id"


def test_gen3_prompts_and_cmdb_do_not_leak_verdicts():
    """Verify that case prompts and CMDB blast_radius do not leak diagnostic answers or verdicts."""
    for filename in ["soc_tier1_interactive.json", "soc_live_mcp_interactive.json"]:
        config_path = ROOT_DIR / "configs" / "evals" / "gen3" / filename
        with open(config_path) as f:
            data = json.load(f)
        for case in data.get("eval_cases", data.get("cases", [])):
            prompt = case["prompt"].lower()
            cmdb_blast = case.get("cmdb_context", {}).get("blast_radius", "").lower()
            for text_block, source in [(prompt, "prompt"), (cmdb_blast, "blast_radius")]:
                assert "rfc-5737" not in text_block, f"{case['eval_id']} {source} leaks RFC-5737"
                assert "revoked by ca" not in text_block, f"{case['eval_id']} {source} leaks revoked certificate"
                assert "qualys scanner" not in text_block and "authorized noise" not in text_block, f"{case['eval_id']} {source} leaks authorized scanner noise"
                assert "isolate host immediately" not in text_block, f"{case['eval_id']} {source} leaks action instruction"
