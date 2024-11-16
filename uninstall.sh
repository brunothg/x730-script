#!/bin/bash

SCRIPT_PATH="${BASH_SOURCE}"
while [ -L "${SCRIPT_PATH}" ]; do
  SCRIPT_DIR="$(cd -P "$(dirname "${SCRIPT_PATH}")" >/dev/null 2>&1 && pwd)"
  SCRIPT_PATH="$(readlink "${SCRIPT_PATH}")"
  [[ ${SCRIPT_PATH} != /* ]] && SCRIPT_PATH="${SCRIPT_DIR}/${SCRIPT_PATH}"
done
SCRIPT_PATH="$(readlink -f "${SCRIPT_PATH}")"
SCRIPT_DIR="$(cd -P "$(dirname -- "${SCRIPT_PATH}")" >/dev/null 2>&1 && pwd)"

# Test is root
if [ "$EUID" -ne 0 ]
then 
    echo "Please run as root"
    exit
fi


# Uninstall systemd units
systemctl disable x730poweroff
systemctl disable x730reboot
systemctl disable --now x730button
rm /etc/systemd/system/x730poweroff.service
rm /etc/systemd/system/x730reboot.service
rm /etc/systemd/system/x730button.service

# Unnstall shell scripts
rm /usr/local/bin/x730shutdown.sh
rm /usr/local/bin/x730button.sh
