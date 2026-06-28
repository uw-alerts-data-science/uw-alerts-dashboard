# GitHub Setup: SSH & Repository Clone

This guide covers installing the GitHub CLI, generating an SSH key, authenticating with GitHub, and cloning the repository. Follow the section for your operating system.

---

## 1. Install Git

### Mac
Git ships with Xcode Command Line Tools. Run the following and follow the prompts if Git is not already installed:
```bash
git --version
```

### Windows
Download and install [Git for Windows](https://git-scm.com/download/win). During installation, select **"Git from the command line and also from 3rd-party software"** when prompted about PATH.

### Linux (Ubuntu/Debian)
```bash
sudo apt update && sudo apt install git
```

---

## 2. Install GitHub CLI

The GitHub CLI (`gh`) lets you authenticate with GitHub from the terminal and simplifies SSH key setup.

### Mac
```bash
brew install gh
```

### Windows
Download the installer from [cli.github.com](https://cli.github.com/) or install via winget:
```powershell
winget install --id GitHub.cli
```

### Linux (Ubuntu/Debian)
```bash
(type -p wget >/dev/null || (sudo apt update && sudo apt install wget -y)) \
  && sudo mkdir -p -m 755 /etc/apt/keyrings \
  && wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg \
     | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
  && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
     | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
  && sudo apt update && sudo apt install gh -y
```

---

## 3. Authenticate with GitHub via SSH

Run the following (same on all platforms):

```bash
gh auth login
```

When prompted:
1. **Where do you use GitHub?** → `GitHub.com`
2. **What is your preferred protocol?** → `SSH`
3. **Generate a new SSH key?** → `Yes` (or select an existing key if you have one)
4. **Enter a passphrase** → optional but recommended
5. **How would you like to authenticate?** → `Login with a web browser`

Follow the browser prompt to complete login. `gh` will upload your public SSH key to GitHub automatically.

Verify the connection:
```bash
ssh -T git@github.com
# Hi <your-username>! You've successfully authenticated...
```

---

## 4. Clone the Repository

```bash
git clone git@github.com:uw-alerts-data-science/uw-alerts-dashboard.git
cd uw-alerts-dashboard
```

---

## 5. Next Steps

Once cloned, follow the [Local Development](../README.md#local-development) section in the README to install dependencies, set up your `.env` file, and start the database.
