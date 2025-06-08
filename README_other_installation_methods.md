
## Older deprecated installation methods

### PIP and PIPX
NEF-Pipelines can also  be installed using pip and pipx

Firstly install pipx if you need to, using the commands for your OS ...

#### OSX

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

#### Windows
1. make sure you have python3 installed
2. check if you have pipx installed by typing `pipx --version` in a command prompt
3. if you don't have pipx installed, install it by typing
```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```
4. close your terminal window and open a new one an type

#### Windows using WSL2

follow the instruction for linux distro of choice inside WSL2...

#### Ubuntu / Mint

```bash
sudo apt install pipx python3-venv
```

#### Fedora / RHEL / Centos/ ROCKY Linux / AlmaLinux

```bash
sudo dnf install pipx
```

#### openSUSE
```bash
sudo zypper install python3-pipx
```

#### Then to install NEF-Pipelines
```bash
pipx install nef-pipelines
```
