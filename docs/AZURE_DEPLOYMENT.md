# Azure for Students full deployment

Status: cloud deployment preparation is complete; the student subscription and interactive authentication are still required. No Azure server has been provisioned yet. The GitHub Pages site remains a read-only report viewer until a separately verified cloud workspace is linked.

## Signup the account owner completes

1. Open https://azure.microsoft.com/en-us/free/students/ and choose Start free.
2. Sign in with a Microsoft account, complete the school-email/student eligibility check, and any requested phone verification.
3. Select Azure for Students, not Students Starter or a pay-as-you-go upgrade. Microsoft advertises no credit card and USD 100 credit usable within 12 months for eligible full-time university students.
4. In https://portal.azure.com/, open Subscriptions and confirm Azure for Students is Active. Keep its spending limit enabled. The credit is finite; a sufficiently large inference VM consumes it even though smaller services have monthly free allowances.
5. Complete the deployment CLI's Microsoft device-code sign-in when shown. Passwords, verification codes other than the displayed device code, and authentication tokens are not needed in chat.

Sources checked 15 October 2026: https://azure.microsoft.com/en-us/free/students/ and https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/azurestudents-subscription-disabled.

## Prepared architecture

One Ubuntu x64 VM runs the real FastAPI application and its background transcription/scoring workers. The built React website is served by the same app; Caddy supplies HTTPS using the Azure public DNS name. The inference port is internal to Docker. Public inbound ports are 80/443; SSH is restricted to the administrator's current address.

The target is initially two CPU cores with 16 GB RAM, subject to actual student quota, permitted regions and availability. A smaller 8 GB option may be tested if needed. The 1-2 GB free micro instances are not an appropriate target for the unchanged medium recognition/alignment stack. No GPU or paid speech API is needed.

Persistent state, anonymous-session ownership and uploads live in `/srv/vocalis/state`; models/cache live in `/srv/vocalis/models`. The initial seed contains only the protected 91 public recordings and ten verified real reports, excluding private microphone and all guest uploads. New guest jobs execute the actual models and persist new results. Seed edits are blocked, upload size is 12 MB and active CPU jobs are bounded. This is a judging prototype, not an identity-based multi-tenant service.

## Deployment sequence handled by the coding agent

1. The isolated Azure CLI is installed at `tools-local/azure-cli`. Set `AZURE_CONFIG_DIR` to the ignored `tools-local/azure-profile`, then authenticate with `python -m azure.cli login --use-device-code`. Keep credentials out of Git and deployment artifacts.
2. Run `scripts/azure_preflight.py` to verify the active student subscription, spending limit and policy regions. Run it again with `--region ALLOWED_REGION --size AVAILABLE_SIZE` to check x64, memory, family/regional quotas and current Linux retail compute price before provisioning. The tool does not create resources or upgrade accounts.
3. Provision one project-tagged resource group and Ubuntu VM in an allowed region, with a 64 GB Standard SSD disk, static public IP/DNS and restricted SSH. Record the actual estimated compute, disk, IP and traffic costs against the student credit. Do not create a GPU VM, paid subscription or unrelated resource.
4. Push the reviewed source, clone the public repository on the VM and pin the deployment commit. Transfer `tmp/azure-cloud-seed/vocalis-public-seed.tar.gz` using the project-owned SSH key, validating the host key through Azure's trusted control plane.
5. Run `bash deploy/azure/install-docker.sh`, then `bash deploy/azure/bootstrap.sh AZURE_DNS_NAME PATH_TO_PUBLIC_SEED_ARCHIVE`. The bootstrap keeps an existing state database, warms real ASR/alignment into persistent storage, builds the full frontend/backend image, and starts the app plus HTTPS proxy with restart policies.
6. Verify actual fresh upload, medium transcription, full scoring, audio playback and exports over HTTPS. Check cross-visitor isolation, mobile pages and the microphone workflow. Confirm frontend/API/model execution have no dependency on localhost or the original tunnel before publishing the new judging URL.

The Linux Docker build, Azure quota/region permissions, certificate issuance and real cloud inference remain unverified until the authenticated server exists. Local validation covers the serving/session guard, database isolation and frontend production build; those checks do not substitute for cloud deployment.

## Credit and judging lifetime

Microsoft's USD 100 student credit is usable within 12 months, not a promise of 12 months of a 16 GB VM. Compute, disk, static IP and traffic can consume credit. Keep the student spending limit enabled and inspect the estimate/credit balance. Stop and deallocate the VM when judging is over; retained disks/IP can still incur charges against credit. Deleting the project resource group removes its data too, so retain needed submissions/recordings first.
