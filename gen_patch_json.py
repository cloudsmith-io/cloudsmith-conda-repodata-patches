"""Script used for generating patch instructions for a Cloudsmith repository and subdir."""

from __future__ import absolute_import, division, print_function

from collections import defaultdict
import copy
import json
import os
from os.path import join, isdir
import sys
import re
import tqdm

import requests

#
# Setup
#

CLOUDSMITH_API_KEY = os.getenv("CLOUDSMITH_API_KEY", "")
CLOUDSMITH_ORG_NAME = os.getenv("CLOUDSMITH_ORG_NAME", "")
CLOUDSMITH_REPO_NAME = os.getenv("CLOUDSMITH_REPO_NAME", "")
CLOUDSMITH_CONDA_CHANNEL_API = (
    f"https://token:{CLOUDSMITH_API_KEY}@conda.cloudsmith.io/{CLOUDSMITH_ORG_NAME}/{CLOUDSMITH_REPO_NAME}"
)

# Include subdirectories for patches to apply to.
SUBDIRS = ("noarch",)
OPERATORS = ["==", ">=", "<=", ">", "<", "!="]

#
# Helpers
#

def has_dep(record, name):
    """Checks if the record contains a particular dependency."""
    return any(dep.split(' ')[0] == name for dep in record.get('depends', ()))

def _replace_pin(old_pin, new_pin, deps, record):
    """Replace an exact pin with a new one."""
    if old_pin in deps:
        i = record['depends'].index(old_pin)
        record['depends'][i] = new_pin

def _rename_dependency(fn, record, old_name, new_name):
    """Rename a specific dependency."""
    depends = record["depends"]
    dep_idx = next(
        (q for q, dep in enumerate(depends)
         if dep.split(' ')[0] == old_name),
        None
    )
    if dep_idx is not None:
        parts = depends[dep_idx].split(" ")
        remainder = (" " + " ".join(parts[1:])) if len(parts) > 1 else ""
        depends[dep_idx] = new_name + remainder
        record['depends'] = depends

def pad_list(l, num):
    if len(l) >= num:
        return l
    return l + ["0"]*(num - len(l))

def get_upper_bound(version, max_pin):
    num_x = max_pin.count("x")
    ver = pad_list(version.split("."), num_x)
    ver[num_x:] = ["0"]*(len(ver)-num_x)
    ver[num_x-1] = str(int(ver[num_x-1])+1)
    return ".".join(ver)

def _relax_exact(fn, record, fix_dep, max_pin=None):
    depends = record.get("depends", ())
    dep_idx = next(
        (q for q, dep in enumerate(depends)
         if dep.split(' ')[0] == fix_dep),
        None
    )
    if dep_idx is not None:
        dep_parts = depends[dep_idx].split(" ")
        if (len(dep_parts) == 3 and \
                not any(dep_parts[1].startswith(op) for op in OPERATORS)):
            if max_pin is not None:
                upper_bound = get_upper_bound(dep_parts[1], max_pin) + "a0"
                depends[dep_idx] = "{} >={},<{}".format(*dep_parts[:2], upper_bound)
            else:
                depends[dep_idx] = "{} >={}".format(*dep_parts[:2])
            record['depends'] = depends


cb_pin_regex = re.compile(r"^>=(?P<lower>\d(\.\d+)*a?),<(?P<upper>\d(\.\d+)*)a0$")

def _pin_stricter(fn, record, fix_dep, max_pin, upper_bound=None):
    depends = record.get("depends", ())
    dep_indices = [q for q, dep in enumerate(depends) if dep.split(' ')[0] == fix_dep]
    for dep_idx in dep_indices:
        dep_parts = depends[dep_idx].split(" ")
        if len(dep_parts) not in [2, 3]:
            continue
        m = cb_pin_regex.match(dep_parts[1])
        if m is None:
            continue
        lower = m.group("lower")
        upper = m.group("upper").split(".")
        if upper_bound is None:
            new_upper = get_upper_bound(lower, max_pin).split(".")
        else:
            new_upper = upper_bound.split(".")
        upper = pad_list(upper, len(new_upper))
        new_upper = pad_list(new_upper, len(upper))
        if tuple(upper) > tuple(new_upper):
            if str(new_upper[-1]) != "0":
                new_upper += ["0"]
            depends[dep_idx] = "{} >={},<{}a0".format(dep_parts[0], lower, ".".join(new_upper))
            if len(dep_parts) == 3:
                depends[dep_idx] = "{} {}".format(depends[dep_idx], dep_parts[2])
            record['depends'] = depends


def _pin_looser(fn, record, fix_dep, max_pin=None, upper_bound=None):
    depends = record.get("depends", ())
    dep_indices = [q for q, dep in enumerate(depends) if dep.split(' ')[0] == fix_dep]
    for dep_idx in dep_indices:
        dep_parts = depends[dep_idx].split(" ")
        if len(dep_parts) not in [2, 3]:
            continue
        m = cb_pin_regex.match(dep_parts[1])
        if m is None:
            continue
        lower = m.group("lower")
        upper = m.group("upper").split(".")

        if upper_bound is None:
            new_upper = get_upper_bound(lower, max_pin).split(".")
        else:
            new_upper = upper_bound.split(".")

        upper = pad_list(upper, len(new_upper))
        new_upper = pad_list(new_upper, len(upper))

        if tuple(upper) < tuple(new_upper):
            if str(new_upper[-1]) != "0":
                new_upper += ["0"]
            depends[dep_idx] = "{} >={},<{}a0".format(dep_parts[0], lower, ".".join(new_upper))
            if len(dep_parts) == 3:
                depends[dep_idx] = "{} {}".format(depends[dep_idx], dep_parts[2])
            record['depends'] = depends

#
# Patching Instructions Generation
#

def _gen_patch_instructions(index, new_index):
    """
    Generate the patch instructions by comparing the unmodifed index 
    (from repodata_from_packages.json) with the new index with the patches applied.
    """
    instructions = {
        "patch_instructions_version": 1,
        "packages": defaultdict(dict),
        "revoke": [],
        "remove": [],
    }

    # diff all items in the index and put any differences in the instructions
    for fn in index:
        assert fn in new_index

        # replace any old keys
        for key in index[fn]:
            assert key in new_index[fn], (key, index[fn], new_index[fn])
            if index[fn][key] != new_index[fn][key]:
                instructions['packages'][fn][key] = new_index[fn][key]

        # add any new keys
        for key in new_index[fn]:
            if key not in index[fn]:
                instructions['packages'][fn][key] = new_index[fn][key]

    return instructions

def _gen_new_index(repodata, subdir):
    """
    Make any changes to the index by adjusting the values directly below.
    This function returns the new index with the adjustments.
    
    Subsequently, the new and old indices are then diff'ed to produce the repodata patches.
    """
    index = copy.deepcopy(repodata["packages"])

    for filename, record in index.items():
        package_name = record["name"]
        package_version = record['version']
        package_deps = record.get("depends", ())

        # ADD PATCHES BELOW.

        # For example to update a pin within a package dependency:
        # 1. Replace pin within test-conda
        # if package_name == "test-conda" and package_version == "11.0.0":
        #     _replace_pin("python >=3.10,<3.11.0a0", "python >=3.10", package_deps, record)

    return index

#
# Run
#

def main():
    # Checks
    if not (
        CLOUDSMITH_API_KEY,
        CLOUDSMITH_ORG_NAME,
        CLOUDSMITH_REPO_NAME,
    ):
        print("Please set your API key (or OIDC token), organization name and repository name.")
        return

    # Step 1. Collect initial repodata for all subdirs.
    repodatas = {}
    for subdir in tqdm.tqdm(SUBDIRS, desc="Downloading repodata"):
        repodata_url = "/".join(
            (CLOUDSMITH_CONDA_CHANNEL_API, subdir, "repodata_from_packages.json"))
        response = requests.get(
            repodata_url,
            timeout=60,
        )
        response.raise_for_status()
        repodatas[subdir] = response.json()

    # Step 2. Create all patch instructions.
    patches_dir = "patches"
    for subdir in SUBDIRS:
        patches_subdir = join(patches_dir, subdir)
        if not isdir(patches_subdir):
            os.makedirs(patches_subdir)

        # Step 2a. Generate a new index.
        new_index = _gen_new_index(repodatas[subdir], subdir)

        # Step 2b. Generate the instructions by diff'ing the indices.
        instructions = _gen_patch_instructions(repodatas[subdir]['packages'], new_index)

        # Step 2c. Output this to patches_subdir so that we bundle the JSON files.
        patch_instructions_path = join(
            patches_subdir, "patch_instructions.json")
        with open(patch_instructions_path, 'w', encoding="utf-8") as fh:
            json.dump(
                instructions, fh, indent=2,
                sort_keys=True, separators=(',', ': '))

if __name__ == "__main__":
    sys.exit(main())