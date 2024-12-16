"""Utility functions for applying the patch instructions."""

#!/usr/bin/env python

def _apply_patch_instructions(repodata, instructions):
    """
    Apply the repodata patch instructions by merging the two dictionaries.
    Code is a simplified version from: https://github.com/conda/conda-index/blob/main/conda_index/index/__init__.py (included in LICENSE).
    For cloudsmith repodata patches, we only requires a small subset of the code.
    Please do not modify this function.
    """
    _merge_or_update_dict(
        repodata.get("packages", {}),
        instructions.get("packages", {}),
        add_missing_keys=False,
    )

    return repodata

def _merge_or_update_dict(
    base, new, add_missing_keys=True
):
    """
    Merges and updates the provided repodata with the patch instructions.
    Code is a simplified version from: https://github.com/conda/conda-index/blob/main/conda_index/utils.py (included in LICENSE).
    For cloudsmith repodata patches, we only requires a small subset of the code.
    Please do not modify this function.
    """
    if base == new:
        return base

    for key, value in new.items():
        if key in base or add_missing_keys:
            base_value = base.get(key, value)
            if hasattr(value, "keys"):
                base_value = _merge_or_update_dict(
                    base_value, value
                )
                base[key] = base_value
            else:
                if value is None and key in base:
                    del base[key]
                else:
                    base[key] = value
    return base