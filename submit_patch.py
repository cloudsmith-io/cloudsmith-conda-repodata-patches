"""Script for submitting the generated patch instructions to your repository."""

from os.path import join, isdir
import requests

from gen_patch_json import CLOUDSMITH_CONDA_CHANNEL_API, SUBDIRS

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Submit patches to your cloudsmith repository.")
    
    parser.add_argument(
        '--subdirs', nargs='*', default=None,
        help='subdir(s) to submit for, default is all')
    args = parser.parse_args()

    if args.subdirs is None:
        subdirs = SUBDIRS
    else:
        subdirs = args.subdirs

    for subdir in subdirs:
        patches_subdir = join("patches", subdir)
        if not isdir(patches_subdir):
            print(f"No generated patches exists for the subdir - {subdir}")
            continue

        patch_instructions_path = join(patches_subdir, "patch_instructions.json")
        with open(patch_instructions_path, 'r', encoding="utf-8") as patch_instructions_file:
           patch_instructions_json = patch_instructions_file.read()

        patch_instructions_url = f"{CLOUDSMITH_CONDA_CHANNEL_API}/{subdir}/patch_instructions.json"

        response = requests.put(
            patch_instructions_url, 
            data=patch_instructions_json, 
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )

        if response.status_code == 201:
            print(f"Patch instructions successfully updated for {subdir}")
        else: 
            print(f"Error updating the patch instructions for {subdir}")