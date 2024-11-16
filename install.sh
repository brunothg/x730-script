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


# Check prequisites
echo "Checking prequisites ..."

for bin in "systemctl" "pinctrl"
do
  if ! type "$bin" &> /dev/null
  then
    echo "$bin ...  missing"
    exit 1
  else
    echo "$bin ... passed"
  fi
done


# Install shell scripts
chmod 755 "$SCRIPT_DIR"/src/*.sh
cp "$SCRIPT_DIR"/src/*.sh /usr/local/bin/


# Install systemd units
chmod 644 "$SCRIPT_DIR"/src/*.service
cp "$SCRIPT_DIR"/src/*.service /etc/systemd/system/

systemctl enable x730poweroff
systemctl enable x730reboot
systemctl enable --now x730button
