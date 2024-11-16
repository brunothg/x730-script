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


# Install shell scripts
chmod 755 "$SCRIPT_DIR"/src/*.sh
cp "$SCRIPT_DIR"/src/*.sh /usr/local/bin/

# Install systemd units
chmod 644 "$SCRIPT_DIR"/src/*.service
cp "$SCRIPT_DIR"/src/*.service /etc/systemd/system/

systemctl enable x730shutdown
systemctl enable --now x730button
