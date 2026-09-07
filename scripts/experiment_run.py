"""Durable launch records and strict artifact identity checks for GCE experiments."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import uuid
from typing import Any

from scripts.serving_config import validate_serving_config


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def configuration_hash(configuration: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(configuration, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Replace one record atomically; interrupted writes retain the previous record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def new_run(configuration: dict[str, Any], output_bucket: str,
            instance_name: str | None = None) -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    flavor = configuration["target"]["flavor"]
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", flavor):
        raise ValueError("Invalid target flavor")
    if not output_bucket.startswith("gs://") or any(c.isspace() for c in output_bucket):
        raise ValueError("Output bucket must be a gs:// URI without whitespace")
    instance_name = instance_name or f"spot-{flavor.replace('.', '-')[:24]}-{run_id}"
    if not re.fullmatch(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?", instance_name):
        raise ValueError("Invalid GCE instance name")
    return {
        "schema_version": 1, "run_id": run_id,
        "configuration_hash": configuration_hash(configuration),
        "configuration": configuration, "instance_name": instance_name,
        "artifact_uri": f"{output_bucket.rstrip('/')}/runs/{run_id}/{flavor}",
        "created_at": now(), "launch_status": "PREPARED",
        "identity_scope": "launch_binding_only",
    }


def load_run(path: Path | str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text())
    validate_run(data)
    return data


def validate_run(data: dict[str, Any]) -> None:
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unsupported launch manifest")
    if not re.fullmatch(r"[0-9a-f]{32}", str(data.get("run_id", ""))):
        raise ValueError("Invalid run ID")
    config = data.get("configuration")
    if not isinstance(config, dict) or configuration_hash(config) != data.get("configuration_hash"):
        raise ValueError("Launch configuration hash mismatch")
    for key in ("project_id", "zone"):
        if not isinstance(config.get(key), str) or not re.fullmatch(r"[a-z0-9-]+", config[key]):
            raise ValueError(f"Invalid {key}")
    source = config.get("source_bundle")
    if source is not None:
        if not isinstance(source, dict):
            raise ValueError("Invalid source bundle configuration")
        for field, length in (("sha256", 64), ("verifier_sha256", 64), ("source_commit", 40)):
            value = source.get(field)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value):
                raise ValueError(f"Invalid source bundle {field}")
        uri = source.get("uri")
        if not isinstance(uri, str) or not re.fullmatch(r"gs://[a-z0-9][a-z0-9._-]*/[^\s*?\[\]#]+", uri) or "|~|" in uri:
            raise ValueError("Invalid source bundle URI")
    serving = config.get("serving_config")
    if serving is not None:
        if source is None:
            raise ValueError("Serving configuration requires a pinned source bundle")
        try:
            validate_serving_config(serving, target=config.get("target"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid serving configuration: {exc}") from exc
    target = config.get("target", {})
    if not isinstance(target, dict):
        raise ValueError("Invalid target configuration")
    flavor = target.get("flavor", "")
    if not isinstance(flavor, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", flavor):
        raise ValueError("Invalid target flavor")
    name = data.get("instance_name", "")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?", name):
        raise ValueError("Invalid instance name")
    uri = data.get("artifact_uri", "")
    if (not isinstance(uri, str) or not uri.startswith("gs://") or any(c.isspace() for c in uri)
            or not uri.endswith(f"/runs/{data['run_id']}/{flavor}")):
        raise ValueError("Artifact URI does not match run identity")


def identity_error(artifact: Any, run: dict[str, Any]) -> str | None:
    """Require identity and reject conflicting duplicate fields, including failures."""
    if not isinstance(artifact, dict):
        return "Artifact must be a JSON object"
    provenance = artifact.get("provenance", {})
    if not isinstance(provenance, dict):
        return "Invalid provenance"
    ids = [v for v in (artifact.get("run_id"), provenance.get("run_id")) if v is not None]
    hashes = [v for v in (artifact.get("configuration_hash"),
                          provenance.get("launch_configuration_hash")) if v is not None]
    if not ids or any(v != run["run_id"] for v in ids):
        return "Missing or mismatched run ID"
    if not hashes or any(v != run["configuration_hash"] for v in hashes):
        return "Missing or mismatched launch configuration hash"
    if artifact.get("flavor", run["configuration"]["target"]["flavor"]) != run["configuration"]["target"]["flavor"]:
        return "Mismatched model flavor"
    return None
