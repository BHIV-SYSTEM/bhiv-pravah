# Full System Demo

Phase 1 trace-sovereignty proof packet: [review_packets/final_convergence.md](review_packets/final_convergence.md)

## Run the demo

Windows PowerShell:
```powershell
.\scripts\run_full_demo.ps1
# optionally tear down after: .\scripts\run_full_demo.ps1 -TearDown
```

Linux / macOS:
```bash
./scripts/run_full_demo.sh
```

## Expected output (high level)
- Services started (Redis, deploy workers, monitors, agents)
- Demo runner logs: initialization, decision path, enforcement, execution
- Pravah stream emission line: `[PRAVAH WATCH] [execution] trace_id=... execution_id=...`
- Final passive snapshot and summary showing `Total events: 1` (or more depending on run)

## What success looks like
- `trace_id` propagated from entry to final snapshot
- `execution_id` assigned and present in Pravah output
- `[X-CALLER=sarathi] accepted` appears in logs
- Pravah shows an `[execution]` event in `review_packets/assets/pravah_stream.txt`

## Notes
- If `http://localhost:5000/process-runtime` is not available, the runtime will fall back to `fallback_safe` and execute `noop`. This is a designed resilience behavior and considered successful for local demo verification.
