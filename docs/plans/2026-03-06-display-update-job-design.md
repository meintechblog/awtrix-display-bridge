# Display Update Job Design

**Problem**

The browser currently calls `POST /api/display/update` and waits for the full AWTRIX update flow. That flow can take longer than the frontend timeout because it includes firmware download, upload, reboot, and version confirmation. The result is a misleading `Fetch is aborted` error in the UI even when the update succeeds.

**Goals**

- Remove raw transport errors from the user-facing update UX.
- Show a clear product-level update state for each display.
- Check firmware status once when the `Displays` page opens.
- Allow a manual re-check from the same central update element.
- Keep the existing bridge-side version comparison and OTA fallback logic.

**Approaches**

1. `Recommended`: async server-side update jobs.
   - The UI starts an update job and polls a dedicated job-status endpoint.
   - The bridge owns the long-running work and exposes phase-based status.
   - This cleanly decouples browser request lifetime from update lifetime.
2. Long browser timeout.
   - Minimal code churn, but still fragile and gives poor progress UX.
3. Fire-and-forget update plus status refresh.
   - Less backend work than jobs, but still ambiguous for the user while rebooting.

**Chosen design**

Use async bridge-managed update jobs.

**Backend**

Add a small in-memory job manager inside the update service:
- `start_update_job(ip)` creates a job id, records the initial state, and runs the update in a worker thread.
- `job_status(job_id)` returns the latest phase, message, progress timestamps, and final result.
- Jobs are short-lived runtime state only; they do not need persistence across bridge restarts.

Add explicit update phases:
- `checking`
- `downloading`
- `uploading`
- `rebooting`
- `verifying`
- `completed`
- `failed`

API shape:
- `GET /api/display/update-status?ip=...`
- `POST /api/display/update/start`
- `GET /api/display/update/job?id=...`

`GET /api/display/update-status` remains the source of truth for “what version is installed vs latest official version”.

**Frontend**

The `Displays` view keeps one central update element per display.

States:
- `Update auf <latest>`: primary CTA if update is available.
- `Aktuell · <latest>`: passive status, but clickable for manual re-check.
- `Prüfe...`: transient state while the initial/manual check runs.
- `Update läuft...`: disabled while backend is executing.
- `Rebootet...` / `Prüfe Version...`: disabled phase states derived from the job.
- `Update fehlgeschlagen`: retry CTA.

Behavior:
- When `Displays` mounts, run one firmware status check.
- Do not poll firmware status every 60s anymore.
- A click on `Aktuell · <latest>` or bare `Update` triggers a manual re-check.
- A click on `Update auf <latest>` starts the async job.
- Once a job finishes, immediately refresh firmware status.

**Error handling**

- Browser aborts are removed from the visible UX because the start request returns immediately.
- Backend job failures are mapped to user-facing messages such as `Update fehlgeschlagen` with the latest error below the CTA.
- If the display becomes unreachable during reboot, that is represented as a normal `rebooting`/`verifying` phase, not as an immediate failure.

**Testing**

Backend:
- Add tests for job creation, phase transitions, completion, and failure.
- Add HTTP API tests for the new start/job endpoints.

Frontend:
- Add tests for initial check on page load.
- Add tests for manual re-check from the central element.
- Add tests for async job polling and phase labels.

