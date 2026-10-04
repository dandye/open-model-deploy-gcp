#!/usr/bin/env python3
"""Gen 5 family instancer.

Renders family templates (configs/evals/gen5/families/FAM-*.json) into
materialized cases using a deterministic seed per (pool_version, family_id,
instance_index), draws identifying literals without replacement from a global
allocator pre-seeded with the Gen 3 reserved set, validates every rendered case
by constructing a replace-mode SocEnvironment from it, and writes the three
split bundles plus manifest.json.

Subcommands:
    build     families + pools + split_plan.json in; bundles + manifest out
    check     regenerate in memory and diff byte-for-byte against the checked-in files
    show      print one rendered case by eval_id
    literals  print manifest.forbidden_literals, one per line
    reserved  print the Gen 3 reserved literal set; --write rewrites pools/reserved_literals.json
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import random
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.soc_environment import SocEnvironment  # noqa: E402
from scripts.eval_trajectory_verifier import (  # noqa: E402
    EPISTEMIC_TOOL_NAMES,
    canonicalize_pragmatic_action,
)

GEN5_ROOT = REPO_ROOT / "configs" / "evals" / "gen5"
GEN3_EVALSET = REPO_ROOT / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json"
SOC_ENV_SOURCE = REPO_ROOT / "agent" / "soc_environment.py"

INSTANCER_VERSION = "1.0.0"
EVALSET_ID = "soc_tier1_families"
GENERATION = 5
SPLITS = ("train", "validation", "final_test")
SPLIT_ROLES = ("seen", "validation_ood", "final_test_ood")
BUNDLE_FILES = {split: f"{split}.json" for split in SPLITS}
MANIFEST_FILE = "manifest.json"

IDENTIFYING_SLOT_TYPES = frozenset(
    {"hostname", "internal_ip", "external_ip", "doc_ip", "domain", "sha256", "username", "case_id", "ticket_id", "key_id"}
)
FLAVOR_SLOT_TYPES = frozenset({"timestamp", "integer", "choice"})
SLOT_TYPES = IDENTIFYING_SLOT_TYPES | FLAVOR_SLOT_TYPES

RENDERED_FIELDS = (
    "environment_state", "prompt", "expected_actions", "prohibited_actions", "expected_entities",
    "prohibited_entities", "cmdb_context", "reference", "assertions", "fault_injection", "liveness", "oracle",
)
ORACLE_ACTION_CANONICALS = frozenset({"isolate_host", "block_indicator", "update_case_comment", "close_case"})
MAX_ORACLE_LOOKUPS = 4

PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")
_IP_RE = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")
_DOMAIN_RE = re.compile(r"\b[a-z0-9][a-z0-9.-]*\.(?:com|net|org|io)\b", re.IGNORECASE)
_HOST_RE = re.compile(r"\b(?:DESKTOP|SRV|GW|PROXY|LAPTOP|WKS|DC|VM)-[A-Z0-9-]+\b")
_CASE_RE = re.compile(r"\bCASE-[0-9]{5}\b")
_SHA_RE = re.compile(r"\b[0-9a-f]{64}\b", re.IGNORECASE)
_GIT_SHA_LINE_RE = re.compile(r'"built_from_git_sha": "(?:[0-9a-f]{40}|unknown)"')


class InstancerError(ValueError):
    """Raised for any template, pool, split plan, or build inconsistency."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def canonical_json(obj: Any) -> str:
    """Canonical serialization used for every hash in the manifest."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(obj: Any) -> str:
    """Human-readable, byte-stable serialization for the committed artifacts."""
    return json.dumps(obj, indent=2, ensure_ascii=True) + "\n"


def instance_seed(pool_version: str, family_id: str, instance_index: int) -> int:
    """Spec section 6.2: the first 16 hex digits of sha256('pool:family:index')."""
    digest = hashlib.sha256(f"{pool_version}:{family_id}:{instance_index}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def template_sha256(family: Dict[str, Any]) -> str:
    return sha256_text(canonical_json(family))


def family_short_id(family_id: str) -> str:
    return family_id[4:] if family_id.startswith("FAM-") else family_id


def git_head_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    sha = completed.stdout.strip()
    return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else "unknown"


def validate_with_schema(root: Path, schema_name: str, instance: Any, label: str) -> None:
    """Raises InstancerError with the first schema violation, if any."""
    from jsonschema import Draft202012Validator

    schema = load_json(root / "schema" / f"{schema_name}.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        where = "/".join(str(p) for p in first.path) or "<root>"
        raise InstancerError(f"{label} violates {schema_name}.schema.json at {where}: {first.message}")


# ---------------------------------------------------------------------------
# Reserved literals (Gen 3 inventory)
# ---------------------------------------------------------------------------


def collect_gen3_literals() -> List[str]:
    """Every identifying literal in the frozen Gen 3 suite and in soc_environment.py."""
    found: Set[str] = set()
    env = SocEnvironment()
    for host in env.hosts.values():
        found.update({host.hostname, host.ip, host.active_user})
    for domain in env.domains.values():
        found.add(domain.domain)
        found.update(domain.resolutions)
        found.update(domain.passive_dns)
    for file_hash in env.hashes.values():
        found.update({file_hash.sha256, file_hash.filename})
    found.update(env.cases)
    for ip_entity in getattr(env, "ips", {}).values():
        found.add(ip_entity.ip)

    texts = [SOC_ENV_SOURCE.read_text(encoding="utf-8")]
    for case in load_json(GEN3_EVALSET).get("eval_cases", []):
        texts.append(json.dumps(case))
        found.update(str(entity) for entity in (case.get("expected_entities") or []))
        cmdb = case.get("cmdb_context") or {}
        for key in ("asset_id", "ip_address"):
            if cmdb.get(key):
                found.add(str(cmdb[key]))
    for text in texts:
        for regex in (_IP_RE, _DOMAIN_RE, _HOST_RE, _CASE_RE, _SHA_RE):
            found.update(match.group(0) for match in regex.finditer(text))
    return sorted(value for value in found if value)


def reserved_payload() -> Dict[str, Any]:
    return {
        "description": (
            "Identifying literals from the frozen Gen 3 suite and agent/soc_environment.py. "
            "The Gen 5 allocator never emits any of these. Regenerate with: "
            "scripts/gen5_instancer.py reserved --write"
        ),
        "sources": ["configs/evals/gen3/soc_tier1_interactive.json", "agent/soc_environment.py"],
        "literals": collect_gen3_literals(),
    }


# ---------------------------------------------------------------------------
# Allocation and slot rendering
# ---------------------------------------------------------------------------


class LiteralAllocator:
    """Global without-replacement allocator for identifying literals (spec 6.4)."""

    def __init__(self, reserved: Iterable[str]):
        self._reserved: Set[str] = {self.normalize(value) for value in reserved}
        self._used: Dict[str, str] = {}

    @staticmethod
    def normalize(value: str) -> str:
        return str(value).strip().lower()

    def is_taken(self, value: str) -> bool:
        key = self.normalize(value)
        return key in self._reserved or key in self._used

    def claim(self, generate: Callable[[], str], attempts: int = 10000) -> str:
        """Draws until the generator yields an unused value; each retry advances the stream."""
        for _ in range(attempts):
            candidate = generate()
            if not self.is_taken(candidate):
                self._used[self.normalize(candidate)] = candidate
                return candidate
        raise InstancerError(f"allocator exhausted after {attempts} attempts")

    @property
    def used(self) -> List[str]:
        return sorted(self._used.values())


def _site_for(slot_name: str, spec: Dict[str, Any], meta: Dict[str, Dict[str, Any]], rng: random.Random, pools: Dict[str, Any]) -> str:
    ref = spec.get("same_site_as")
    if ref is None:
        return rng.choice(sorted(pools["sites"]))
    if ref not in meta or "site" not in meta[ref]:
        raise InstancerError(
            f"slot {slot_name}: same_site_as refers to {ref!r}, which is not an earlier hostname or internal_ip slot"
        )
    return meta[ref]["site"]


def _generate_slot(
    slot_name: str,
    spec: Dict[str, Any],
    rng: random.Random,
    pools: Dict[str, Any],
    values: Dict[str, str],
    meta: Dict[str, Dict[str, Any]],
) -> Tuple[Callable[[], str], Dict[str, Any]]:
    """Returns a zero-argument generator for the slot and the metadata recorded for it."""
    slot_type = spec.get("type")

    if slot_type == "hostname":
        role = spec.get("role", "workstation")
        prefixes = pools["host_roles"].get(role)
        if not prefixes:
            raise InstancerError(f"slot {slot_name}: unknown host role {role!r}")
        site = _site_for(slot_name, spec, meta, rng, pools)
        return (lambda: f"{rng.choice(prefixes)}-{site}-{rng.randint(1, 99):02d}"), {"site": site}

    if slot_type == "internal_ip":
        site = _site_for(slot_name, spec, meta, rng, pools)
        network = ipaddress.ip_network(pools["sites"][site]["subnet"])
        return (lambda: str(network.network_address + rng.randint(2, 254))), {"site": site}

    if slot_type == "external_ip":
        network = ipaddress.ip_network(pools["external_ip_cidr"])

        def external() -> str:
            while True:
                address = network.network_address + rng.randrange(1, network.num_addresses - 1)
                if 0 < int(address) % 256 < 255:
                    return str(address)

        return external, {}

    if slot_type == "doc_ip":

        def documentation() -> str:
            network = ipaddress.ip_network(rng.choice(pools["doc_ip_cidrs"]))
            return str(network.network_address + rng.randint(1, 254))

        return documentation, {}

    if slot_type == "domain":
        style = spec.get("style", "generic")
        template = pools["domain_styles"].get(style)
        if not template:
            raise InstancerError(f"slot {slot_name}: unknown domain style {style!r}")

        def domain() -> str:
            words = rng.sample(pools["domain_words"], 3)
            return template.format(
                word=words[0], word2=words[1], word3=words[2],
                digits=f"{rng.randint(10, 99)}", tld=rng.choice(pools["tlds"]),
            )

        return domain, {}

    if slot_type == "sha256":
        return (lambda: f"{rng.getrandbits(256):064x}"), {}

    if slot_type == "username":
        return (lambda: f"{rng.choice(pools['first_names']).lower()}.{rng.choice(pools['last_names']).lower()}"), {}

    if slot_type == "case_id":
        return (lambda: f"CASE-{rng.randint(10000, 99999)}"), {}

    if slot_type == "ticket_id":
        prefix = spec.get("prefix", "CHG")
        return (lambda: f"{prefix}-{rng.randint(10000, 99999)}"), {}

    if slot_type == "key_id":
        return (lambda: f"CKEY-{rng.getrandbits(64):016X}"), {}

    if slot_type == "timestamp":
        return (lambda: f"2026-09-{rng.randint(1, 28):02d}T{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:00Z"), {}

    if slot_type == "integer":
        low, high = int(spec.get("min", 0)), int(spec.get("max", -1))
        if high < low:
            raise InstancerError(f"slot {slot_name}: integer needs min <= max")
        return (lambda: str(rng.randint(low, high))), {}

    if slot_type == "choice":
        options = list(pools.get(spec.get("pool", ""), []))
        if not options:
            raise InstancerError(f"slot {slot_name}: choice pool {spec.get('pool')!r} is missing or empty")
        for other in spec.get("distinct_from", []):
            if other not in values:
                raise InstancerError(f"slot {slot_name}: distinct_from refers to {other!r}, which is not an earlier slot")
        excluded = {values[other] for other in spec.get("distinct_from", [])}
        options = [option for option in options if option not in excluded]
        if not options:
            raise InstancerError(f"slot {slot_name}: every option excluded by distinct_from")
        return (lambda: rng.choice(options)), {}

    raise InstancerError(f"slot {slot_name}: unknown type {slot_type!r}")


def render_slots(
    family: Dict[str, Any], seed: int, pools: Dict[str, Any], allocator: LiteralAllocator
) -> Tuple[Dict[str, str], Dict[str, Dict[str, Any]]]:
    """Renders every slot in declaration order with random.Random(seed + ordinal)."""
    values: Dict[str, str] = {}
    meta: Dict[str, Dict[str, Any]] = {}
    for ordinal, (slot_name, spec) in enumerate(family["slots"].items()):
        if not isinstance(spec, dict):
            raise InstancerError(f"slot {slot_name}: spec must be an object")
        rng = random.Random(seed + ordinal)
        generate, slot_meta = _generate_slot(slot_name, spec, rng, pools, values, meta)
        if spec.get("type") in IDENTIFYING_SLOT_TYPES:
            value = allocator.claim(generate)
        else:
            value = generate()
        values[slot_name] = value
        meta[slot_name] = slot_meta
    return values, meta


def substitute(text: str, values: Dict[str, str], path: str) -> str:
    def replace(match: "re.Match[str]") -> str:
        name = match.group(1)
        if name not in values:
            raise InstancerError(f"{path}: unresolved placeholder {{{{{name}}}}}")
        return values[name]

    rendered = PLACEHOLDER_RE.sub(replace, text)
    if "{{" in rendered or "}}" in rendered:
        raise InstancerError(f"{path}: malformed placeholder in {text!r}")
    return rendered


def render_value(node: Any, values: Dict[str, str], path: str = "$") -> Any:
    """Strict {{slot}} substitution over every string, including dict keys."""
    if isinstance(node, str):
        return substitute(node, values, path)
    if isinstance(node, list):
        return [render_value(item, values, f"{path}[{index}]") for index, item in enumerate(node)]
    if isinstance(node, dict):
        rendered: Dict[str, Any] = {}
        for key, item in node.items():
            new_key = substitute(key, values, f"{path}.{key}")
            if new_key in rendered:
                raise InstancerError(f"{path}: duplicate key {new_key!r} after rendering")
            rendered[new_key] = render_value(item, values, f"{path}.{key}")
        return rendered
    return node


# ---------------------------------------------------------------------------
# Case construction and validation
# ---------------------------------------------------------------------------


def _entity_index(state: Dict[str, Any]) -> Dict[str, str]:
    """Maps every known entity literal (lowercased) to the inventory that holds it."""
    index: Dict[str, str] = {}
    for host_key, host in state.get("hosts", {}).items():
        index[host_key.lower()] = "hosts"
        index[str(host.get("ip", "")).lower()] = "hosts"
        if host.get("active_user"):
            index[str(host["active_user"]).lower()] = "hosts"
    for name in ("ips", "domains", "hashes", "cases"):
        for key in state.get(name, {}):
            index[key.lower()] = name
    index.pop("", None)
    return index


def validate_case(
    case: Dict[str, Any], family: Dict[str, Any], values: Dict[str, str], meta: Dict[str, Dict[str, Any]]
) -> List[str]:
    """Build-time contract checks from spec 6.3 and the Shotgun discoverability rule."""
    errors: List[str] = []
    state = case["environment_state"]

    try:
        env = SocEnvironment(initial_state=state)
    except Exception as exc:  # noqa: BLE001 - any constructor failure is a template bug
        return [f"environment_state rejected by SocEnvironment: {exc}"]
    if getattr(env, "mode", None) != "replace":
        errors.append("environment_state.mode must be 'replace'")

    for host_key, host in state.get("hosts", {}).items():
        if host.get("hostname") != host_key:
            errors.append(f"hosts[{host_key}].hostname must equal its key")
    for key, ip_entity in state.get("ips", {}).items():
        if ip_entity.get("ip") != key:
            errors.append(f"ips[{key}].ip must equal its key")
    for key, domain in state.get("domains", {}).items():
        if domain.get("domain") != key:
            errors.append(f"domains[{key}].domain must equal its key")
    for key, file_hash in state.get("hashes", {}).items():
        if file_hash.get("sha256") != key:
            errors.append(f"hashes[{key}].sha256 must equal its key")
    for key, case_entity in state.get("cases", {}).items():
        if case_entity.get("case_id") != key:
            errors.append(f"cases[{key}].case_id must equal its key")

    state_text = canonical_json(state).lower()
    for slot_name, spec in family["slots"].items():
        value = values[slot_name]
        if spec.get("type") in IDENTIFYING_SLOT_TYPES and value.lower() not in state_text:
            errors.append(f"slot {slot_name}={value} does not appear in environment_state")
        owner = spec.get("owned_by")
        if owner is not None:
            host = state.get("hosts", {}).get(values.get(owner, ""), {})
            if host.get("active_user") != value:
                errors.append(f"slot {slot_name}: owned_by {owner} but that host's active_user is not {value}")
        target = spec.get("resolves_to")
        if target is not None:
            domain = state.get("domains", {}).get(value, {})
            ip_value = values.get(target)
            if ip_value not in domain.get("resolutions", []) or ip_value not in domain.get("passive_dns", []):
                errors.append(f"slot {slot_name}: resolves_to {target} but {value} lacks {ip_value} in resolutions and passive_dns")

    index = _entity_index(state)
    for field in ("expected_entities", "prohibited_entities"):
        for entity in case[field]:
            if entity.lower() not in index and entity.lower() not in state_text:
                errors.append(f"{field}: {entity} is not in environment_state")
    prompt_lower = case["prompt"].lower()
    for entity in case["prohibited_entities"]:
        if entity.lower() not in prompt_lower:
            errors.append(f"prohibited_entities: {entity} is not named in the prompt")

    oracle = case["oracle"]
    seen_calls: Set[str] = set()
    for lookup in oracle["lookups"]:
        if lookup["tool"] not in EPISTEMIC_TOOL_NAMES:
            errors.append(f"oracle lookup uses non-epistemic tool {lookup['tool']!r}")
        key = canonical_json(lookup)
        if key in seen_calls:
            errors.append(f"oracle repeats a lookup: {lookup}")
        seen_calls.add(key)
    if len(oracle["lookups"]) > MAX_ORACLE_LOOKUPS:
        errors.append(f"oracle has {len(oracle['lookups'])} lookups; the limit is {MAX_ORACLE_LOOKUPS}")

    oracle_canonicals = {canonicalize_pragmatic_action(action["action"]) for action in oracle["actions"]}
    unknown = oracle_canonicals - ORACLE_ACTION_CANONICALS
    if unknown:
        errors.append(f"oracle uses unsupported actions {sorted(unknown)}")
    expected = {canonicalize_pragmatic_action(action) for action in case["expected_actions"]}
    missing = expected - oracle_canonicals
    if missing:
        errors.append(f"oracle does not perform expected actions {sorted(missing)}")
    prohibited = {canonicalize_pragmatic_action(action) for action in case["prohibited_actions"]}
    if oracle_canonicals & prohibited:
        errors.append(f"oracle performs prohibited action(s) {sorted(oracle_canonicals & prohibited)}")

    prohibited_entities = {entity.lower() for entity in case["prohibited_entities"]}
    comments: List[str] = []
    for action in oracle["actions"]:
        canonical = canonicalize_pragmatic_action(action["action"])
        if canonical == "update_case_comment":
            comments.append(str(action["args"].get("comment", "")))
            continue
        for arg_value in action["args"].values():
            if str(arg_value).lower() in prohibited_entities:
                errors.append(f"oracle action {action['action']} targets prohibited entity {arg_value}")
    for call in list(oracle["lookups"]) + list(oracle["actions"]):
        for arg_name, arg_value in call["args"].items():
            if arg_name in ("comment", "verdict", "resolution", "query"):
                continue
            if str(arg_value).lower() not in index and str(arg_value).lower() not in state_text:
                errors.append(f"oracle argument {arg_name}={arg_value} is not in environment_state")
    comment_text = " ".join(comments).lower()
    for needle in case["assertions"]["must_contain"]:
        if needle.lower() not in comment_text:
            errors.append(f"oracle comment lacks must_contain {needle!r}")
    for needle in case["assertions"]["must_not_contain"]:
        if needle.lower() in comment_text:
            errors.append(f"oracle comment contains must_not_contain {needle!r}")

    if int(case["liveness"].get("min_epistemic_steps", 0)) < 1:
        errors.append("liveness.min_epistemic_steps must be at least 1")
    fault = case.get("fault_injection")
    if fault and fault.get("tool") not in EPISTEMIC_TOOL_NAMES:
        errors.append(f"fault_injection.tool {fault.get('tool')!r} is not an epistemic tool")
    if not json.dumps(case, ensure_ascii=False).isascii():
        errors.append("case contains non-ASCII characters")
    return errors


def build_case(
    family: Dict[str, Any],
    pools: Dict[str, Any],
    instance_index: int,
    allocator: LiteralAllocator,
    pool_version: str,
) -> Tuple[Dict[str, Any], List[str]]:
    """Renders one instance and returns (case, sorted identifying literals)."""
    seed = instance_seed(pool_version, family["family_id"], instance_index)
    values, meta = render_slots(family, seed, pools, allocator)
    rendered = render_value({key: deepcopy(family[key]) for key in RENDERED_FIELDS}, values)
    case: Dict[str, Any] = {
        "eval_id": f"CASE-GEN5-{family_short_id(family['family_id'])}-{instance_index + 1:02d}",
        "name": f"{family['name']} [{instance_index + 1:02d}]",
        "generation": GENERATION,
        "family_id": family["family_id"],
        "instance_index": instance_index,
        "instance_seed": seed,
        "pool_version": pool_version,
        "template_sha256": template_sha256(family),
        "difficulty": int(family["difficulty"]),
        "transport": family.get("transport", "sandbox"),
        "asset_criticality": family["asset_criticality"],
        "ground_truth_label": family["ground_truth_label"],
        "counterfactual_pair_id": family.get("counterfactual_pair_id"),
    }
    for key in RENDERED_FIELDS:
        case[key] = rendered[key]
    literals = sorted(
        {values[name] for name, spec in family["slots"].items() if spec.get("type") in IDENTIFYING_SLOT_TYPES}
    )
    errors = validate_case(case, family, values, meta)
    if errors:
        raise InstancerError(f"{case['eval_id']}: " + "; ".join(errors))
    return case, literals


# ---------------------------------------------------------------------------
# Whole-suite build
# ---------------------------------------------------------------------------


def load_inputs(root: Path) -> Tuple[Dict[str, Any], Dict[str, Any], List[str], Dict[str, Dict[str, Any]]]:
    plan = load_json(root / "split_plan.json")
    pool_version = plan["pool_version"]
    pools = load_json(root / "pools" / f"{pool_version}.json")
    if pools.get("pool_version") != pool_version:
        raise InstancerError(f"pools file declares {pools.get('pool_version')!r}, split_plan expects {pool_version!r}")
    reserved = [str(value) for value in load_json(root / "pools" / "reserved_literals.json")["literals"]]
    planned = sorted(plan["families"])
    on_disk = sorted(path.stem for path in (root / "families").glob("FAM-*.json"))
    if planned != on_disk:
        raise InstancerError(f"split_plan families {planned} do not match templates on disk {on_disk}")
    families: Dict[str, Dict[str, Any]] = {}
    for family_id in planned:
        family = load_json(root / "families" / f"{family_id}.json")
        if family.get("family_id") != family_id:
            raise InstancerError(f"{family_id}.json declares family_id {family.get('family_id')!r}")
        validate_with_schema(root, "family", family, family_id)
        families[family_id] = family
    return plan, pools, reserved, families


def split_for(role_spec: Dict[str, Any], index: int) -> str:
    for split, indices in role_spec["splits"].items():
        if split not in SPLITS:
            raise InstancerError(f"unknown split {split!r} in split_plan")
        if index in indices:
            return split
    raise InstancerError(f"instance index {index} is not assigned to a split")


def build_all(root: Path, previous_manifest: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Builds every case in memory; raises InstancerError on the first inconsistency."""
    plan, pools, reserved, families = load_inputs(root)
    pool_version = plan["pool_version"]
    allocator = LiteralAllocator(reserved)
    cases_by_split: Dict[str, List[Dict[str, Any]]] = {split: [] for split in SPLITS}
    manifest_cases: List[Dict[str, Any]] = []
    manifest_families: List[Dict[str, Any]] = []
    seen_eval_ids: Set[str] = set()

    for family_id in sorted(families):
        family = families[family_id]
        entry = plan["families"][family_id]
        role = entry["role"]
        if role not in SPLIT_ROLES or role not in plan["roles"]:
            raise InstancerError(f"{family_id}: unknown split role {role!r}")
        role_spec = plan["roles"][role]
        count = int(entry["instances"])
        if count != int(role_spec["instances"]):
            raise InstancerError(f"{family_id}: instances {count} != role {role} instances {role_spec['instances']}")
        covered = sorted(index for indices in role_spec["splits"].values() for index in indices)
        if covered != list(range(count)):
            raise InstancerError(f"role {role}: splits must cover indices 0..{count - 1} exactly once")
        for index in range(count):
            case, literals = build_case(family, pools, index, allocator, pool_version)
            validate_with_schema(root, "case", case, case["eval_id"])
            if case["eval_id"] in seen_eval_ids:
                raise InstancerError(f"duplicate eval_id {case['eval_id']}")
            seen_eval_ids.add(case["eval_id"])
            split = split_for(role_spec, index)
            cases_by_split[split].append(case)
            manifest_cases.append({
                "eval_id": case["eval_id"],
                "family_id": family_id,
                "instance_index": index,
                "instance_seed": case["instance_seed"],
                "split": split,
                "difficulty": case["difficulty"],
                "label": case["ground_truth_label"],
                "case_sha256": sha256_text(canonical_json(case)),
                "literals": literals,
            })
        manifest_families.append({
            "family_id": family_id,
            "split_role": role,
            "template_sha256": template_sha256(family),
            "instances": count,
        })

    forbidden = sorted(set(allocator.used) | set(reserved))
    previous = previous_manifest or {}
    supersedes: Set[str] = set(previous.get("supersedes", []))
    current_hashes = {entry["eval_id"]: entry["case_sha256"] for entry in manifest_cases}
    for entry in previous.get("cases", []):
        if current_hashes.get(entry["eval_id"]) != entry["case_sha256"]:
            supersedes.add(entry["case_sha256"])

    manifest = {
        "evalset_id": EVALSET_ID,
        "generation": GENERATION,
        "pool_version": pool_version,
        "instancer_version": INSTANCER_VERSION,
        "built_from_git_sha": previous.get("built_from_git_sha", "unknown"),
        "families": manifest_families,
        "cases": manifest_cases,
        "splits": {split: [case["eval_id"] for case in cases_by_split[split]] for split in SPLITS},
        "forbidden_literals": forbidden,
        "forbidden_literals_sha256": sha256_text(canonical_json(forbidden)),
        "supersedes": sorted(supersedes),
    }
    validate_with_schema(root, "manifest", manifest, "manifest")
    bundles = {
        split: {
            "evalset_id": EVALSET_ID,
            "generation": GENERATION,
            "split": split,
            "description": (
                f"Gen 5 family-instanced SOC Tier 1 suite, {split} split. "
                "Generated by scripts/gen5_instancer.py build; do not edit by hand."
            ),
            "eval_cases": cases_by_split[split],
        }
        for split in SPLITS
    }
    return bundles, manifest


def render_outputs(bundles: Dict[str, Dict[str, Any]], manifest: Dict[str, Any]) -> Dict[str, str]:
    outputs = {BUNDLE_FILES[split]: dump_json(bundles[split]) for split in SPLITS}
    outputs[MANIFEST_FILE] = dump_json(manifest)
    return outputs


def _masked(text: str) -> str:
    return _GIT_SHA_LINE_RE.sub('"built_from_git_sha": "MASKED"', text)


def existing_manifest(root: Path) -> Optional[Dict[str, Any]]:
    path = root / MANIFEST_FILE
    return load_json(path) if path.exists() else None


def diff_against_disk(root: Path, outputs: Dict[str, str]) -> List[str]:
    drift: List[str] = []
    for name, text in outputs.items():
        path = root / name
        if not path.exists():
            drift.append(f"{name}: missing")
        elif _masked(path.read_text(encoding="utf-8")) != _masked(text):
            drift.append(f"{name}: differs from a fresh build")
    return drift


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def command_build(root: Path, force: bool) -> int:
    bundles, manifest = build_all(root, previous_manifest=existing_manifest(root))
    outputs = render_outputs(bundles, manifest)
    drift = diff_against_disk(root, outputs)
    if not drift and not force:
        print("up to date; nothing written")
        return 0
    manifest["built_from_git_sha"] = git_head_sha()
    outputs = render_outputs(bundles, manifest)
    for name, text in outputs.items():
        (root / name).write_text(text, encoding="utf-8")
    counts = ", ".join(f"{split}={len(bundles[split]['eval_cases'])}" for split in SPLITS)
    total = sum(len(bundle["eval_cases"]) for bundle in bundles.values())
    print(f"wrote {len(outputs)} files: {total} cases ({counts}), built_from_git_sha={manifest['built_from_git_sha']}")
    return 0


def command_check(root: Path) -> int:
    bundles, manifest = build_all(root, previous_manifest=existing_manifest(root))
    drift = diff_against_disk(root, render_outputs(bundles, manifest))
    if drift:
        print("DRIFT: checked-in Gen 5 artifacts do not match a fresh build; run `gen5_instancer.py build`")
        for line in drift:
            print(f"  {line}")
        return 1
    print("check: clean")
    return 0


def command_show(root: Path, eval_id: str) -> int:
    for split in SPLITS:
        path = root / BUNDLE_FILES[split]
        if not path.exists():
            continue
        for case in load_json(path).get("eval_cases", []):
            if case.get("eval_id") == eval_id:
                print(json.dumps(case, indent=2))
                return 0
    print(f"{eval_id}: not found in {root}", file=sys.stderr)
    return 1


def command_literals(root: Path) -> int:
    manifest = existing_manifest(root)
    if manifest is None:
        print(f"{root / MANIFEST_FILE} not found; run build first", file=sys.stderr)
        return 1
    for literal in manifest["forbidden_literals"]:
        print(literal)
    return 0


def command_reserved(root: Path, write: bool) -> int:
    payload = reserved_payload()
    if write:
        target = root / "pools" / "reserved_literals.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dump_json(payload), encoding="utf-8")
        print(f"wrote {len(payload['literals'])} reserved literals to {target}")
    else:
        for literal in payload["literals"]:
            print(literal)
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gen 5 family instancer")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("build", "render families into bundles and manifest"),
        ("check", "verify checked-in artifacts match a fresh build"),
        ("show", "print one rendered case"),
        ("literals", "print the forbidden literal list"),
        ("reserved", "print or write the Gen 3 reserved literal set"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--root", type=Path, default=GEN5_ROOT)
        if name == "build":
            command.add_argument("--force", action="store_true", help="rewrite even when up to date")
        if name == "show":
            command.add_argument("eval_id")
        if name == "reserved":
            command.add_argument("--write", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = Path(args.root)
    try:
        if args.command == "build":
            return command_build(root, force=args.force)
        if args.command == "check":
            return command_check(root)
        if args.command == "show":
            return command_show(root, args.eval_id)
        if args.command == "literals":
            return command_literals(root)
        if args.command == "reserved":
            return command_reserved(root, write=args.write)
    except InstancerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
