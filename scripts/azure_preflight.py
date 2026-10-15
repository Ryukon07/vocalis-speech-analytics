"""Read-only student subscription, region, quota and VM-price checks."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import httpx

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools-local/azure-cli/Scripts/python.exe"
PROFILE = ROOT / "tools-local/azure-profile"


def azure(*arguments):
    environment = {**os.environ, "AZURE_CONFIG_DIR": str(PROFILE)}
    result = subprocess.run([str(CLI), "-m", "azure.cli", *arguments, "--output", "json", "--only-show-errors"], env=environment, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout) if result.stdout.strip() else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", help="An allowed Azure region; no resources are created.")
    parser.add_argument("--size", default="Standard_E2as_v5", help="Prefer 2 CPU cores and 16 GB RAM for the unchanged models.")
    arguments = parser.parse_args()
    accounts = azure("account", "list", "--refresh")
    active = [account for account in accounts if account["state"] == "Enabled"]
    if not active:
        raise SystemExit("No active Azure subscription is authenticated. Complete Azure for Students signup and device-code login first.")
    students = []
    for account in active:
        details = azure("rest", "--method", "GET", "--url", f"https://management.azure.com/subscriptions/{account['id']}?api-version=2022-12-01")
        policies = details.get("subscriptionPolicies", {})
        if "student" in policies.get("quotaId", "").lower():
            students.append((account, policies))
    if len(students) != 1:
        raise SystemExit("Expected exactly one active student subscription. Do not use another paid subscription automatically.")
    account, policies = students[0]
    if policies.get("spendingLimit", "").lower() != "on":
        raise SystemExit("The student spending limit is not reported On. Inspect subscription protections before provisioning.")
    azure("account", "set", "--subscription", account["id"])
    assignments = azure("policy", "assignment", "list", "--scope", "/subscriptions/" + account["id"])
    allowed = None
    for assignment in assignments:
        for key, parameter in assignment.get("parameters", {}).items():
            if "location" in key.lower() and isinstance(parameter.get("value"), list):
                locations = set(parameter["value"])
                allowed = locations if allowed is None else allowed & locations
    result = dict(status="preflight_only_no_resources_created", student_subscription=True, spending_limit=policies.get("spendingLimit"), allowed_regions=sorted(allowed) if allowed is not None else "Inspect Azure Policy if a region is rejected", proposed_size=arguments.size)
    if arguments.region:
        if allowed is not None and arguments.region not in allowed:
            raise SystemExit("Requested region is not allowed by the student's subscription policy.")
        skus = azure("vm", "list-skus", "--location", arguments.region, "--resource-type", "virtualMachines", "--size", arguments.size, "--all")
        matching = [sku for sku in skus if sku["name"] == arguments.size]
        assert len(matching) == 1, "VM size not listed in this region."
        sku = matching[0]
        assert not sku.get("restrictions"), "This VM size has subscription/location restrictions."
        capabilities = {item["name"]: item["value"] for item in sku["capabilities"]}
        assert capabilities.get("CpuArchitectureType", "x64") == "x64", "The prepared deployment targets x64."
        assert float(capabilities["MemoryGB"]) >= 8, "Do not provision the 1-2 GB free micro VM for these models."
        usage = azure("vm", "list-usage", "--location", arguments.region)
        family = next((item for item in usage if item["name"]["value"].lower() == sku["family"].lower()), None)
        cores = next((item for item in usage if item["name"]["value"].lower() == "cores"), None)
        required = int(capabilities["vCPUs"])
        assert family is not None and family["limit"] - family["currentValue"] >= required, "Insufficient VM-family CPU quota."
        assert cores is not None and cores["limit"] - cores["currentValue"] >= required, "Insufficient regional CPU quota."
        response = httpx.get("https://prices.azure.com/api/retail/prices", params={"$filter": f"armRegionName eq '{arguments.region}' and armSkuName eq '{arguments.size}' and priceType eq 'Consumption'"}, timeout=45)
        prices = [item for item in response.raise_for_status().json()["Items"] if item.get("productName", "").startswith("Virtual Machines ") and "Windows" not in item["productName"] and "Spot" not in item["meterName"] and "Low Priority" not in item["meterName"] and item["unitOfMeasure"] == "1 Hour"]
        assert prices, "No Linux compute price was found; estimate costs before provisioning."
        price = min(item["retailPrice"] for item in prices)
        result.update(region=arguments.region, memory_gb=float(capabilities["MemoryGB"]), cpu_cores=required, linux_compute_usd_per_hour=price, seven_day_compute_usd=round(price * 24 * 7, 2), excludes="Disk, public IP, backup and network traffic; usage consumes the finite student credit.")
    target = ROOT / "tmp/azure-planning"
    target.mkdir(exist_ok=True)
    (target / "subscription-preflight.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
