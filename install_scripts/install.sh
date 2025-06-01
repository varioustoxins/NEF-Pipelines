
NO_UV=100
UV_DIDNT_UPDATE=101
USER_CANCELLED=102
NEF_PIPELINES_DIDNT_INSTALL=200
UV_MIN_VERSION=0.5.20

yes="${NEF_PIPELINES_AUTO_INSTALL:-no}"

while [[ $# -gt 0 ]]; do
  case $1 in
    -y|--yes)
      yes="yes"
      shift
      ;;
    -h|--help)
      echo "install NEF-Pipelines"
      echo
      echo "options:"
      echo
      echo "--yes / -y - answer yes to questions"
      echo "--help / -h - show this message"
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
    echo "Not running in a terminal, since there is no user interaction the answer is no"
    answer=no
  else
    read answer
  fi

  if [[ "$answer" != "${answer#[Nn]}" && "$answer" != "" ]] ; then
      echo installation cancelled...
      exit $USER_CANCELLED
  fi
fi


# check UV exists
UV_EXISTS=false
if command -v uv &> /dev/null ; then
  UV_EXISTS=true
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

if $UV_EXISTS ; then
  UV_VERSION=$(uv --version | cut -d' ' -f2)
  if ! version_gt $UV_VERSION $UV_MIN_VERSION ; then
    echo "uv version is outdated, please update to version $UV_MIN_VERSION or higher"
    echo "to update use uv self update or reinstall if its not supported by you current uv version"
    exit 1
  fi
else
  echo
  echo installing UV...
  echo
  if $CURL_EXISTS ; then
      curl -LsSf https://astral.sh/uv/install.sh | sh
  elif $WGET_EXISTS ; then
      wget -qO- https://astral.sh/uv/install.sh | sh
  fi
fi

# check UV exists
UV_EXISTS=false
if command -v uv &> /dev/null ; then
  UV_EXISTS=true
fi

echo
echo "* uv installed"
echo "* updating and installing nef-pipelines"
echo

if ! $UV_EXISTS ; then
  echo "!! failed to install UV please contact the the developers at the nef-pipelines"
  echo "!! github repository https://github.com/varioustoxins/NEF-Pipelines and"
  echo "!! create an issue"

  exit $NO_UV
fi

UV_VERSION=$(uv --version | cut -d' ' -f2)
if ! version_gt $UV_VERSION $UV_MIN_VERSION ; then
    echo "* uv version is outdated, updating..."
    uv self update

    UV_VERSION=$(uv --version | cut -d' ' -f2)
    if ! version_gt $UV_VERSION $UV_MIN_VERSION ; then
        echo "!! uv failed to update please contact the the developers at the nef-pipelines"
        echo "!! github repository https://github.com/varioustoxins/NEF-Pipelines and"
        echo "!! create an issue"
        exit $UV_DIDNT_UPDATE
    fi
fi

# check if nef pipelines exists
NEF_PIPELINES_EXISTS=false
if command -v nef &> /dev/null ; then
  NEF_PIPELINES_EXISTS=true
fi

if $NEF_PIPELINES_EXISTS and  ; then
  echo "* nef pipelines is installed, trying to update nef pipelines..."
  current_version=$( nefl help about  --version )
  output="$(uv tool update nef-pipelines 2>&1)"
  echo "* $output"
  new_version=$( nefl help about  --version )
  echo $current_version -> $new_version
else
  uv tool install nef-pipelines --with streamfitter --with rich --python 3.11
fi
  # check if nef pipelines exists
  NEF_PIPELINES_EXISTS=false
  if command -v nef &> /dev/null ; then
    NEF_PIPELINES_EXISTS=true
  fi

  if ! $NEF_PIPELINES_EXISTS ; then
    echo "!! nef-pipelines failed to install please contact the the developers at the nef-pipelines"
    echo "!! github repository https://github.com/varioustoxins/NEF-Pipelines and"
    echo "!! create an issue"

    exit $NEF_PIPELINES_DIDNT_INSTALL
fi

current_version=$( nefl help about  --version )
echo "* nef pipelines shoud be installed and upto date at $current_version"
