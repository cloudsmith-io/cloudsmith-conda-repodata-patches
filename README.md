### About cloudsmith-conda-repodata-patches
- A repository containing two scripts to patch conda repodata for your cloudsmith repository. 
- It is very similar to the [bioconda-repodata-patches](https://github.com/bioconda/bioconda-repodata-patches) repository (which itself is based on [conda-forge-repository-patches](https://github.com/conda-forge/conda-forge-repodata-patches-feedstock)). 
- Thank you to conda-forge, bioconda and conda contributors. The license (BSD-3) reflects this.

### Usage 

Setup: 
- Fork this repository to your organization.
- Intialise (or create) a python environment. To install the required dependencies use `pip install -r requirements.txt`.
- Copy the `.env.example` template into a `.env` file and initialise the variables with the organization, repository and token/key you'd like to use. Note that the token you are using must be linked to a user/service account that has write access to the repository. Once complete (if running locally), run `source .env` in order for the variables to be used by child processes (i.e the python scripts). 

Adding a patch: 
- In the `gen_patch_json.py` file add the subdirectories (the list of Conda architectures) that currently exist in your cloudsmith repository to the `SUBDIRS` variable. 
- Within the `_gen_new_index` method, add the patch. See the first example (`Replace pin with test-conda`) within this method for how to do this. Note that this is a very basic example, you are free to use the existing helper methods (or create your own!) to create a more complex patch. 
- To test that the patch produces the changes you desire, run the `show_diff.py` script. This outputs the changes that the patch instructions will make to the `repodata.json` (index) per `subdir` for your repository. 

Generating the patch instructions: 
- Once you are content with the changes that the newly added patch will make, run the `gen_patch_json.py` script. Locally, this will generate a `patch_instructions.json` file per subdirectory in a `patches` directory. 
- The `patch_instructions.json` file will follow this exact format, with the package modifications stored within the `packages` key: 
    ```
    {
    "packages": {},
    "patch_instructions_version": 1,
    "remove": [],
    "revoke": []
    }
    ```
- Once you are content with the instructions, run `python submit_patch.py`. This sends a PUT request for each of the newly generated patch instructions per `subdir` to your repository.
- The next time the `repodata.json` is retrieved from the Cloudsmith, the index should have the patches applied.

### Notes
- We encourage you to fork this repository and push all your patches to your forked repository. 
- An ideal setup: 
   1. Require pull request reviews for your repository. 
   2. To submit a patch, open a PR with your patch added to the `gen_patch_json.py` file. Create a CI/CD job which outputs the `diff` (from the `show_diff.py` script) whenever a PR is opened. 
   3. Create another CI/CD job which runs on merges to `main`. This should run the `gen_patch_json.py` script. 
   4. This job could also run the `submit_patch.py` script to update the patch instructions for the specified Cloudsmith repository and `subdir`. 
- The `patch_instructions.json` does support removals and revocations (`remove` and `revoke`). However, we encourage users not to populate these keys. Instead, please either delete or quarantine the package within your Cloudsmith repository. If an attempt is made to submit patch instructions to Cloudsmith with either of these keys populated you will receive a validation error.
- We encourage contributions and ideas for this repository, please open an issue or PR if you'd like to make a change! :) 