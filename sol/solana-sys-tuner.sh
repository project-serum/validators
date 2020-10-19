#!/usr/bin/env bash
set -ex

#shellcheck source=/dev/null
#. /home/sol/service-env.sh
PATH=/home/sol/.local/share/solana/install/active_release/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin

exec solana-sys-tuner --user sol
