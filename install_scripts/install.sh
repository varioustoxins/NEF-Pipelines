
NO_UV=100
UV_DIDNT_UPDATE=101
USER_CANCELLED=102
NEF_PIPELINES_DIDNT_INSTALL=200
UV_MIN_VERSION=0.5.20
PYTHON_VERSION=3.11
# The deprecated `sklearn` stub package (sklearn==0.0.post12) is pulled in as a transitive
# dependency somewhere in the nef-pipelines/streamfitter dependency chain. We have not been
# able to identify which package requires it - neither nef-pipelines nor streamfitter import
# sklearn directly, and it does not appear in their declared dependencies or lock files.
# Without this env var, the sklearn stub refuses to build and the entire install fails.
# Setting it here allows the stub to install silently as a no-op phantom dependency.
export SKLEARN_ALLOW_DEPRECATED_SKLEARN_PACKAGE_INSTALL=True

yes="${NEF_PIPELINES_AUTO_INSTALL:-no}"
test_pypi="no"
INSTALL_MCP="false"

while [[ $# -gt 0 ]]; do
  case $1 in
    -y|--yes)
      yes="yes"
      shift
      ;;
    --test-pypi)
      test_pypi="yes"
      shift
      ;;
    --mcp-server)
      INSTALL_MCP="true"
      shift # Remove --mcp-server from processing
      ;;
    -h|--help)
      echo "install NEF-Pipelines"
      echo
      echo "options:"
      echo
      echo "--yes / -y   - answer yes to questions"
      echo "--test-pypi  - install from test.pypi.org instead of pypi.org (for testing releases)"
      echo "--mcp-server - install the MCP server (experimental take great care!)"
      echo "--help / -h  - show this message"
      exit 0
      shift
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

if [[ $yes == "no" ]] ; then
  # check if the user wants to go ahead
  echo "This script will install or update UV and then use UV to install and update NEF-Pipelines,"
  echo "would you like to go ahead Y[es]/N[o] default=Y[es]?"

  if ! [ -t 0 ]; then
    echo "Not running in a terminal, since there is no user interaction the answer is yes"
    answer=yes
  else
    read answer
  fi

  if [[ "$answer" != "${answer#[Nn]}" && "$answer" != "" ]] ; then
      echo installation cancelled...
      exit $USER_CANCELLED
  fi
fi

# Define the package target based on the flag
if [[ "$INSTALL_MCP" == "true" ]]; then
  # Use brackets to include the extra defined in setup.cfg
  PACKAGE_SPEC="nef-pipelines[mcp]"
  echo "* MCP server support requested."
else
  PACKAGE_SPEC="nef-pipelines"
fi

# check UV exists
UV_EXISTS=false
if command -v uv &> /dev/null ; then
  UV_EXISTS=true
  UV_PATH=`command -v uv`
fi

if ! $UV_EXISTS ; then
  if [ -x $HOME/.local/bin/uv ] ; then
    UV_EXISTS=true
    UV_PATH=${HOME}/.local/bin/uv
  fi
fi

# check curl exists
CURL_EXISTS=false
if command -v curl &> /dev/null ; then
  CURL_EXISTS=true
fi

# check curl exists
WGET_EXISTS=false
if command -v wget &> /dev/null ; then
  WGET_EXISTS=true
fi

version_gt() {
  [ "$(printf '%s\n' "$@" | sort -V | head -n 1)" != "$1" ]
}

DID_UV_INSTALL=false
if [[ $UV_EXISTS  == "true" ]] ; then
  UV_VERSION=$( $UV_PATH --version | cut -d' ' -f2)
  if ! version_gt $UV_VERSION $UV_MIN_VERSION ; then
    echo "!! uv version is outdated, please update to version $UV_MIN_VERSION or higher"
    echo "!! to update use uv self update or reinstall if uv self update is not supported"
    echo "!! by you current uv version"
    exit 1
  fi
else
  echo
  echo installing uv...
  echo
  if [[ $CURL_EXISTS == "true" ]]; then
      curl -LsSf https://astral.sh/uv/install.sh | sh && DID_UV_INSTALL=true
  elif [[ $WGET_EXISTS == "true" ]]; then
      wget -qO- https://astral.sh/uv/install.sh | sh && DID_UV_INSTALL=true
  fi
fi

# check UV exists
UV_EXISTS=false
if command -v uv &> /dev/null ; then
  UV_EXISTS=true
  UV_PATH=`command -v uv`
fi

if [[ $UV_EXISTS  == "false" ]] ; then
  if [ -x ${HOME}/.local/bin/uv ] ; then
    UV_EXISTS=true
    UV_PATH=${HOME}/.local/bin/uv
  fi
fi

if [[ $UV_EXISTS  == "false" ]] ; then
  echo cannot find uv
  exit $NO_UV
fi

if [[ $UV_EXISTS == "true" ]]; then
  echo
  echo "* uv installed"
  echo "* updating and installing nef-pipelines"
  echo
else
  echo "!! failed to install uv, please try the installation a couple of times"
  echo "!! more if your internet connection is poor!"
  echo "!! if the problem persists please contact the the developers at the nef-pipelines"
  echo "!! github repository https://github.com/varioustoxins/NEF-Pipelines and"
  echo "!! create an issue"

  exit $NO_UV
fi

if [[ $DID_UV_INSTALL  ==  "true" ]]; then
  echo * making sure uv is on the path using: uv tool update-shell
  $UV_PATH tool update-shell
fi

UV_VERSION=$( $UV_PATH --version | cut -d' ' -f2)
if ! version_gt $UV_VERSION $UV_MIN_VERSION ; then
    echo "* uv version is outdated, updating..."
    $UV_PATH self update

    UV_VERSION=$($UV_PATH --version | cut -d' ' -f2)
    if ! version_gt $UV_VERSION $UV_MIN_VERSION ; then

        echo "!! uv failed to update, please try the installation a couple of times"
        echo "!! more if your internet connection is poor!"
        echo "!! if the problem persists please contact the the developers at the nef-pipelines"
        echo "!! github repository https://github.com/varioustoxins/NEF-Pipelines and"
        echo "!! create an issue"
        exit $UV_DIDNT_UPDATE
    fi
fi

# check if nef pipelines exists
NEF_PIPELINES_EXISTS=false
if command -v nef &> /dev/null ; then
  NEF_PIPELINES_EXISTS=true
  NEF_PATH=`command -v nef`
fi

if [[ $NEF_PIPELINES_EXISTS == "false" ]] ; then
  if [ -x ${HOME}/.local/bin/nef ] ; then
    NEF_PIPELINES_EXISTS=true
    NEF_PATH=${HOME}/.local/bin/nef
  fi
fi

if [[ $NEF_PIPELINES_EXISTS == "true" ]] ; then
  echo "* nef pipelines is installed, trying to update nef pipelines..."
  current_version=$( $NEF_PATH version )
  if [[ $test_pypi == "yes" ]]; then
    echo "* installing from test.pypi.org..."
    $UV_PATH tool install "${PACKAGE_SPEC}" --with streamfitter --python ${PYTHON_VERSION} --reinstall  \
      --index "https://test.pypi.org/simple/" --index-strategy unsafe-best-match
  else
    $UV_PATH tool install "${PACKAGE_SPEC}" --with streamfitter --python ${PYTHON_VERSION} --reinstall
  fi
  new_version=$( $NEF_PATH version )
  echo "* updated: $current_version -> $new_version"
else
  if [[ $test_pypi == "yes" ]]; then
    echo "* installing from test.pypi.org..."
    $UV_PATH tool install "${PACKAGE_SPEC}" --with streamfitter --python ${PYTHON_VERSION} \
      --index "https://test.pypi.org/simple/" --index-strategy unsafe-best-match --force
  else
    $UV_PATH tool install "${PACKAGE_SPEC}" --with streamfitter --python ${PYTHON_VERSION} --force
  fi
fi

# check if nef pipelines exists
NEF_PIPELINES_EXISTS=false
if command -v nef &> /dev/null ; then
  NEF_PIPELINES_EXISTS=true
  NEF_PATH=`command -v nef`
fi

if [[ $NEF_PIPELINES_EXISTS != "true" ]] ; then
  if [ -x ${HOME}/.local/bin/nef ] ; then
    NEF_PIPELINES_EXISTS=true
    NEF_PATH=${HOME}/.local/bin/nef
  fi
fi

if ! $NEF_PIPELINES_EXISTS ; then
  echo "!! nef-pipelines failed to install, please try the installation a couple of times"
  echo "!! more if your internet connection is poor!"
  echo "!! if the problem persists please contact the the developers at the nef-pipelines"
  echo "!! github repository https://github.com/varioustoxins/NEF-Pipelines and"
  echo "!! create an issue"

  exit $NEF_PIPELINES_DIDNT_INSTALL
fi

current_version=$( $NEF_PATH version )
echo "* nef pipelines should be installed and upto date at $current_version"
echo ""
echo "*YOU MAY NEED TO CLOSE THE SHELL AND REOPEN IT to get nef to run as a command"
