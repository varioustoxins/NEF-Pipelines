#!/bin/bash
# this script uses versionner and tox

# Function to display help
show_help() {
    echo "Usage: $0 [OPTION]"
    echo "Release the package to PyPI."
    echo ""
    echo "Options:"
    echo "  --no-bump    Skip version bumping and tagging."
    echo "  --help       Show this help message."
}

# Parse options
BUMP_VERSION=true
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --no-bump) BUMP_VERSION=false ;;
        --help) show_help; exit 0 ;;
        *) echo "Unknown parameter passed: $1"; show_help; exit 1 ;;
    esac
    shift
done

# check for uncommitted or auto stash
git update-index --refresh >/dev/null
git diff-index --quiet HEAD --

if [[ $? -ne 0 ]]; then
	echo "ERROR: the repo is dirty clean it before building!"
    exit 1
fi

# define where the version file is found
VERSION_FILE=src/nef_pipelines/VERSION

# change to the correct working directory
cd /Users/garythompson/Dropbox/nef_pipelines/nef_pipelines

# clear dists but don't complain if its empty
if [ -n "$ZSH_VERSION" ]; then
  setopt localoptions rmstarsilent
fi
rm -rf dist/* || true

if [ "$BUMP_VERSION" = true ]; then
    echo "Bumping version and tagging..."
    # increase version and tag it
    ver --file $VERSION_FILE up --patch

    # grab the version
    VERSION=$(ver --file $VERSION_FILE | awk '{print $3}')

    # update the version in the repo
    git add src/nef_pipelines/VERSION
    git add pyproject.toml
    git commit -m "updated version to $VERSION" --no-verify

    ver --file $VERSION_FILE tag
else
    echo "Skipping version bump..."
    # grab current version for the stash message
    VERSION=$(ver --file $VERSION_FILE | awk '{print $3}')
fi

# stash any uncommited changes to avoid version+1 errors
stash_message="stashed-for-pypi-drop-${VERSION}-$(date +%s)"
git stash --message "${stash_message}"

# build and publish
tox -e build  # to build your package distribution
tox -e publish -- --repository pypi

git stash list | grep -q "${stash_message}"
if [[ $? -eq 0 ]]; then
  # unstash uncommitted changes
  git stash pop
fi
