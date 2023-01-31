
# define wehere the version file is found
VERSION_FILE=src/nef_pipelines/VERSION

# cheange to the correct working directory
cd /Users/garythompson/Dropbox/nef_pipelines/nef_pipelines

#clear dists but don't complain if its empty
rm -rf  dist/* || true

# increase version and tag it
ver  --file $VERSION_FILE  up --patch
ver  --file $VERSION_FILE tag

# grab the version
VERSION=`ver --file $VERSION_FILE |  awk '{print $3}'`

# update the version  in the repo
git add src/nef_pipelines/VERSION
git commit -m "updated version to $VERSION"

# stash any uncommited changes to avoid version+1 errors
git stash

#build and publish
tox -e build  # to build your package distribution
tox -e publish -- --repository pypi

# unstash uncommitted changes
git stash pop
