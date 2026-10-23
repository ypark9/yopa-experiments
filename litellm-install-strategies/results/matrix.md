# Install strategy matrix (local index)
Package: `supplydemo` clean=1.0.0 upload=2026-10-21T10:44:22.902887Z / tampered=1.1.0 upload=2026-10-21T11:40:00.000000Z
Incident window simulation: 2026-10-21T11:39:51Z .. ~13:23 UTC; mid probe at 2026-10-21T12:00:00Z
| strategy | outcome | version | cook.pth | marker |
|---|---|---|---|---|
| `unpinned_pip` | installed_tampered | 1.1.0 | True | True |
| `pin_eq_bad` | installed_tampered | 1.1.0 | True | True |
| `pin_eq_clean` | installed_clean | 1.0.0 | False | False |
| `require_hashes_clean_only` | installed_clean | 1.0.0 | False | False |
| `require_hashes_bad_with_clean_hash` | refused | None | False | False |
| `uv_exclude_newer_before_incident` | installed_clean | 1.0.0 | False | False |
| `uv_exclude_newer_mid_window` | installed_tampered | 1.1.0 | True | True |
| `pip_uploaded_prior_to_before_incident` | installed_clean | 1.0.0 | False | False |
| `pip_uploaded_prior_to_mid_window` | installed_tampered | 1.1.0 | True | True |
