#!/bin/bash
# this script uses versionner and tox

# Function to display help
show_help() {
    echo "Usage: $0 <aphorism> [OPTION]"
    echo "Release the package to PyPI."
    echo ""
    echo "Arguments:"
    echo "  aphorism     Release aphorism (required, quote if it contains spaces)"
    echo ""
    echo "Options:"
    echo "  --no-bump    Skip version bumping and tagging."
    echo "  --help       Show this help message."
}

# Require aphorism as first argument
if [[ "$#" -eq 0 || "$1" == --* ]]; then
    echo "ERROR: aphorism is required as the first argument"
    echo "  example: $0 \"seeing the nef for the trees\""
    exit 1
fi
APHORISM="$1"
shift

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

    # update the version and aphorism in the repo
    echo "$APHORISM" > src/nef_pipelines/APHORISM
    git add src/nef_pipelines/VERSION
    git add src/nef_pipelines/APHORISM
    git add pyproject.toml
    git commit -m "updated version to $VERSION: $APHORISM" --no-verify

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
tox -e publish -- --repository pypi --skip-existing

git stash list | grep -q "${stash_message}"
if [[ $? -eq 0 ]]; then
  # unstash uncommitted changes
  git stash pop
fi
