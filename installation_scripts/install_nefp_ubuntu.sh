#!/bin/bash

sudo apt --yes install python3-pip
sudo apt --yes install pipx
pip install --upgrade wheel setuptools
pipx install nef-pipelines
pipx inject nef-pipelines rich
if ! grep -q 'pipx path setup!' ${HOME}/.bashrc
then
    echo  '# pipx path setup!' >> ${HOME}/.bashrc
    echo 'export PATH=${HOME}/.local/bin:${PATH}' >> ${HOME}/.bashrc
fi
