#this script uses versionner and tox
# add check for uncommitted or auto stash
git update-index --refresh >/dev/null
git diff-index --quiet HEAD --


if [[ $? -ne 0 ]]; then
	echo "ERROR: the repo is dirty clean it before building!"
    exit 1
fi

echo got here

# define where the version file is found
VERSION_FILE=src/nef_pipelines/VERSION

# change to the correct working directory
cd /Users/garythompson/Dropbox/nef_pipelines/nef_pipelines

#clear dists but don't complain if its empty
if [ -n "$ZSH_VERSION" ]; then
  setopt localoptions rmstarsilent
fi
rm -rf  dist/* || true

# increase version and tag it
ver  --file $VERSION_FILE  up --patch

# grab the version
VERSION=`ver --file $VERSION_FILE |  awk '{print $3}'`

# update the version  in the repo
git add src/nef_pipelines/VERSION
git add pyproject.toml
git commit -m "updated version to $VERSION" --no-verify

ver  --file $VERSION_FILE tag

# stash any uncommited changes to avoid version+1 errors
stash_message="stashed-for-pypi-drop-${VERSION}-`date +%s`"
git stash --message ${stash_message}

#build and publish
tox -e build  # to build your package distribution
tox -e publish -- --repository pypi

git stash list  | grep -q ${stash_message}
if [[ $? -eq 0 ]]; then
  # unstash uncommitted changes
  git stash pop
fi
