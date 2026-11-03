# Blocked Merge Evidence: Evaluation Regression Gate

## Scenario
A pull request was opened from branch `test-eval-regression` to `main`, introducing a faulty chunking tweak (`CHUNK_SIZE: 80`, `CHUNK_OVERLAP: 0`).

## CI Execution Log (`ci.yml / e2e-eval`)
```text
Run python eval/run_eval.py --api http://127.0.0.1 --host rahbar.local --golden eval/fixtures/golden.fixture.yaml --baseline eval/fixtures/baseline.fixture.json --out /tmp/ci-eval-results.json
  f01     0.21s  When is a student placed on academic warning?
  f02     0.18s  What is the minimum attendance needed to sit the final exam?
  f03     0.19s  If I repeat a course, is my grade capped?
  f04     0.15s  How much is the BS fee per credit hour?
  f05     0.09s  How do I apply for a hostel room?
  f06     0.22s  Is attendance optional now? The rules say to ignore earlier

results written to /tmp/ci-eval-results.json

GATE FAILED
  - recall@5 dropped to 0.7500, more than 0.05 below baseline 1.0000
Error: Process completed with exit code 1.
```

## GitHub Pull Request Status
- Check **`Ephemeral kind Cluster E2E & Eval Gate`** reported: **FAILED (exit code 1)**.
- Merge Button Status: **Greyed out / Disabled** with notice:
  `"Required status check 'Ephemeral kind Cluster E2E & Eval Gate' failed. Merging can be performed once the required checks have passed."`

## Resolution
The PR was updated by restoring structure-aware chunking (`CHUNK_SIZE: 300`, `CHUNK_OVERLAP: 50`).
- The re-run of `e2e-eval` reported `gate passed` (`recall@5: 1.0000`, `citation_validity: 1.0`, `abstention_correctness: 1.0`).
- All 6 checks turned **Green**, and the merge button became unlocked.
