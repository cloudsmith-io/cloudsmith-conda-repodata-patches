"""Script used for showing the difference that a patch makes."""

#!/usr/bin/env python

import bz2
import difflib
import json
import os
import requests

from gen_patch_json import _gen_new_index, _gen_patch_instructions, SUBDIRS, CLOUDSMITH_CONDA_CHANNEL_API
from utils import _apply_patch_instructions


CACHE_DIR = os.environ.get(
    "CACHE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
)

def show_record_diffs(subdir, ref_repodata, new_repodata):
    for name, ref_pkg in ref_repodata["packages"].items():
        new_pkg = new_repodata["packages"].get(name, {})
        # license_family may be present for newer packages, ignore it in the diff
        ref_pkg.pop("license_family", None)
        new_pkg.pop("license_family", None)
        if ref_pkg == new_pkg:
            continue
        print(f"{subdir}::{name}")
        ref_lines = json.dumps(ref_pkg, indent=2).splitlines()
        new_lines = json.dumps(new_pkg, indent=2).splitlines()
        for ln in difflib.unified_diff(ref_lines, new_lines, n=0, lineterm=''):
            if ln.startswith('+++') or ln.startswith('---') or ln.startswith('@@'):
                continue
            print(ln)

def do_subdir(subdir, raw_repodata_filepath, ref_repodata_filepath):
    with bz2.open(raw_repodata_filepath) as fh:
        raw_repodata = json.load(fh)
    with bz2.open(ref_repodata_filepath) as fh:
        ref_repodata = json.load(fh)
    new_index = _gen_new_index(raw_repodata, subdir)
    instructions = _gen_patch_instructions(raw_repodata['packages'], new_index)
    raw_repodata["packages.conda"] = {}
    new_repodata = _apply_patch_instructions(raw_repodata, instructions)
    show_record_diffs(subdir, ref_repodata, new_repodata)

def download_subdir(subdir, raw_repodata_filepath, ref_repodata_filepath):
    raw_url = f"{CLOUDSMITH_CONDA_CHANNEL_API}/{subdir}/repodata_from_packages.json.bz2"
    print("Downloading repodata_from_packages.json for:", subdir)
    raw_repodata_response = requests.get(raw_url, timeout=60)
    raw_repodata_response.raise_for_status()
    with open(raw_repodata_filepath, "wb") as file:
            file.write(raw_repodata_response.content)

    ref_url = f"{CLOUDSMITH_CONDA_CHANNEL_API}/{subdir}/repodata.json.bz2"
    print("Downloading repodata.json for:", subdir)
    ref_repodata_response = requests.get(ref_url, timeout=60)
    ref_repodata_response.raise_for_status()
    with open(ref_repodata_filepath, "wb") as file:
            file.write(ref_repodata_response.content)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="show repodata changes from the current gen_patch_json")
    parser.add_argument(
        '--subdirs', nargs='*', default=None,
        help='subdir(s) show, default is all')
    parser.add_argument(
        '--use-cache', action='store_true',
        help='use cached repodata files, rather than downloading them')
    args = parser.parse_args()

    if args.subdirs is None:
        subdirs = SUBDIRS
    else:
        subdirs = args.subdirs

    for subdir in subdirs:
        subdir_dir = os.path.join(CACHE_DIR, subdir)
        if not os.path.exists(subdir_dir):
            os.makedirs(subdir_dir)
        raw_repodata_path = os.path.join(subdir_dir, "repodata_from_packages.json.bz2")
        ref_repodata_path = os.path.join(subdir_dir, "repodata.json.bz2")
        if not args.use_cache:
            download_subdir(subdir, raw_repodata_path, ref_repodata_path)
        do_subdir(subdir, raw_repodata_path, ref_repodata_path)