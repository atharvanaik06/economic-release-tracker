# Sample Research Bundle

This directory demonstrates the complete Phase 6 output for a four-country, two-variable annual macroeconomic panel.

The sample is generated from deterministic World Bank-shaped fixtures. It does not call a live provider and must not be interpreted as a current release. Its purpose is to let reviewers inspect the product contract immediately: data, frozen recipe, validation, codebook, citations, lineage, manifest, and checksums.

Regenerate it from the repository root:

```bash
PYTHONPATH=src .venv/bin/python scripts/generate_sample_bundle.py
```

Verify all files from the build directory:

```bash
shasum -a 256 -c checksums.sha256
```

An identical environment and source tree produces the same logical dataset checksum. Parquet byte encoding may vary across library versions, which is why the manifest records the application version and also carries the format-independent dataset checksum.
