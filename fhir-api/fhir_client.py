"""
FHIR R4 API Client for healthcare resource management.

Provides a lightweight wrapper around the FHIR RESTful API specification
(HL7 FHIR R4) with built-in request logging and structured error handling.
Supports CRUD operations and FHIR search against any R4-compliant server.
"""

import requests
import time
import json


class FHIRClient:
    """FHIR R4 client with request logging and OperationOutcome error parsing."""

    def __init__(self, base_url="https://hapi.fhir.org/baseR4"):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json",
        }
        self.call_log = []

    def _log_call(self, method, url, status_code, elapsed_ms):
        self.call_log.append({
            "method": method,
            "url": url.replace(self.base_url, ""),
            "status": status_code,
            "time_ms": round(elapsed_ms),
        })

    def create(self, resource_type, resource_data):
        """POST a new resource. Returns the server-assigned resource with ID."""
        url = f"{self.base_url}/{resource_type}"
        start = time.time()
        response = requests.post(url, headers=self.headers, json=resource_data)
        self._log_call("POST", url, response.status_code, (time.time() - start) * 1000)

        if response.status_code == 201:
            return response.json()
        self._handle_error("CREATE", resource_type, response)

    def update(self, resource_type, resource_id, resource_data):
        """PUT a resource to a specific ID (create or replace)."""
        url = f"{self.base_url}/{resource_type}/{resource_id}"
        resource_data["id"] = resource_id
        start = time.time()
        response = requests.put(url, headers=self.headers, json=resource_data)
        self._log_call("PUT", url, response.status_code, (time.time() - start) * 1000)

        if response.status_code in (200, 201):
            return response.json()
        self._handle_error("UPDATE", f"{resource_type}/{resource_id}", response)

    def create_or_find(self, resource_type, resource_data, search_params):
        """
        Idempotent create — search first, return existing if found, else create.
        Handles 412 (duplicate detection) and 410 (soft-deleted) via PUT upsert.
        """
        bundle = self.search(resource_type, search_params)
        entries = bundle.get("entry", [])
        if entries:
            existing = entries[0]["resource"]
            existing["_reused"] = True
            return existing

        try:
            return self.create(resource_type, resource_data)
        except Exception as e:
            if "412" in str(e):
                import re
                match = re.search(rf"{resource_type}/(\d+)", str(e))
                if match:
                    rid = match.group(1)
                    # Resource may be soft-deleted (410) — PUT restores it
                    result = self.update(resource_type, rid, resource_data)
                    result["_reused"] = True
                    return result
            raise

    def read(self, resource_type, resource_id):
        """GET a single resource by type and ID."""
        url = f"{self.base_url}/{resource_type}/{resource_id}"
        start = time.time()
        response = requests.get(url, headers=self.headers)
        self._log_call("GET", url, response.status_code, (time.time() - start) * 1000)

        if response.status_code == 200:
            return response.json()
        self._handle_error("READ", f"{resource_type}/{resource_id}", response)

    def search(self, resource_type, params=None):
        """Search resources via FHIR query parameters. Returns a Bundle."""
        url = f"{self.base_url}/{resource_type}"
        start = time.time()
        response = requests.get(url, headers=self.headers, params=params)
        self._log_call("GET", url, response.status_code, (time.time() - start) * 1000)

        if response.status_code == 200:
            return response.json()
        self._handle_error("SEARCH", resource_type, response)

    def delete(self, resource_type, resource_id):
        """DELETE a resource by type and ID."""
        url = f"{self.base_url}/{resource_type}/{resource_id}"
        start = time.time()
        response = requests.delete(url, headers=self.headers)
        self._log_call("DELETE", url, response.status_code, (time.time() - start) * 1000)

        if response.status_code in (200, 204):
            return True
        self._handle_error("DELETE", f"{resource_type}/{resource_id}", response)

    def _handle_error(self, operation, target, response):
        """Parse FHIR OperationOutcome and raise with diagnostic context."""
        try:
            outcome = response.json()
            if "issue" in outcome:
                issues = [
                    issue.get("diagnostics", issue.get("details", {}).get("text", "Unknown"))
                    for issue in outcome["issue"]
                ]
                detail = "; ".join(issues)
            else:
                detail = json.dumps(outcome, indent=2)
        except (ValueError, KeyError):
            detail = response.text

        raise Exception(
            f"FHIR {operation} failed on {target} "
            f"[{response.status_code}]: {detail}"
        )

    def get_call_summary(self):
        """Return chronological log of all API calls in this session."""
        return self.call_log


if __name__ == "__main__":
    client = FHIRClient()
    url = f"{client.base_url}/metadata"
    response = requests.get(url, headers={"Accept": "application/fhir+json"})

    if response.status_code == 200:
        meta = response.json()
        print(f"Connected to: {meta.get('implementation', {}).get('description', 'FHIR Server')}")
        print(f"FHIR version: {meta.get('fhirVersion', 'Unknown')}")
        print("Status: OK")
    else:
        print(f"Connection failed: {response.status_code}")
