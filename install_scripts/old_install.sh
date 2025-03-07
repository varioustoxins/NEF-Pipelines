#!/bin/bash

UV_EXISTS=false
if command -v uv &> /dev/null ; then
  UV_EXISTS=true
fi

UV_MIN_VERSION=0.5.20

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
fi


if ! $UV_EXISTS ; then

  echo "Checking for rust installation..."
  echo ""

  if command -v cargo &> /dev/null ; then
      echo "cargo is already installed, trying to use you current installation"
      echo "if installation of nef-piplines fails, please remove it and run this script again"
      echo  "to uninstall cargo run:"
      echo "     rustup self uninstall"
      echo "or use your package manager if you installed it via that route"

  else
      echo "Installing cargo"
      curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
      source $HOME/.cargo/env
  fi

  if ! command -v cargo &> /dev/null ; then
      echo "cargo installation failed"
      echo "contact the developers for help"
      exit 1
  fi

  echo "installing uv"
  echo ""

  curl -LsSf https://astral.sh/uv/install.sh | sh

fi

if ! command -v uv &> /dev/null ; then
      echo "uv installation failed"
      echo "contact the developers for help"
      exit 1
fi


check_nef_pipelines_exists() {
  if command -v nef &> /dev/null ; then
    nef_version=$(nef help about --version 2>&1)
    echo true
  else
    echo false
  fi
}



nef_piplines_exists=$(check_nef_pipelines_exists)

if $nef_piplines_exists ; then


  nef_version=$(nef help about --version 2>&1)
  echo "nef-pipelines is already installed at version ${nef_version}, nothing to do!"
  exit 0

else
  echo "installing nef-pipelines"
  echo ""

  uv tool install nef-pipelines --quiet

  nef_piplines_exists=$(check_nef_pipelines_exists)
  if $nef_piplines_exists ; then

    nef_version=$(nef help about --version 2>&1)
    echo "nef-pipelines is now installed at version ${nef_version}"
    echo "you can now use nef-pipelines by running the command nef"
    exit 0
  else
    echo "nef-pipelines installation failed..."
    echo "contact the developers for help with any error output"
    exit 1
  fi
fi
#else
#  echo "installing nef-pipelines"
#  echo ""
#
#  uv tool install nef-pipelines --quiet
#
#  nef_piplines_exists=$(check_nef_pipelines_exists)
#  echo $nef_pipelines_exists
##  if [ $nef_pipelines_exists -eq 1] ; then
##
##    nef_version=$(nef help about --version 2>&1)
##    echo "nef-pipelines is now installed at version ${nef_version}"
##    echo "you can now use nef-pipelines by running the command nef"
##    #exit 0
##  fi
#fi
