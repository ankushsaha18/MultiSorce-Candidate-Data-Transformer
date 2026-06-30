# Sample Inputs

Bundled sample files for end-to-end CLI runs and local testing.

## Files

| File | Description |
|------|-------------|
| `recruiter_csv/ada_lovelace.csv` | Structured recruiter export for Ada Lovelace |
| `resume_pdf/ada_lovelace.pdf` | Unstructured resume PDF for the same candidate |

Both sources describe the same person with overlapping and complementary fields. The merge engine prefers resume values on singleton conflicts and unions list fields (emails, phones, skills) deterministically.

## Example

```bash
python main.py \
  --csv samples/recruiter_csv/ada_lovelace.csv \
  --resume samples/resume_pdf/ada_lovelace.pdf \
  --config configs/default_projection.json \
  --output outputs/sample_output.json
```

See the root [README.md](../README.md) for additional projection configs and test commands.
