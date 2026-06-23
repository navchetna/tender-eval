#!/bin/sh
# Ensure the artifact output directory is writable by the running user.
# This matters when the bind-mounted host directory is owned by a different UID.
mkdir -p /home/user/out
chmod 777 /home/user/out
exec "$@"
