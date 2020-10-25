#!/usr/bin/env bash
set -ex

#shellcheck source=/dev/null
#. ~/service-env.sh
PATH=/home/sol/.local/share/solana/install/active_release/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin

TRUSTED_VALIDATOR_PUBKEYS=(7Np41oeYqPefeNQEHSv1UDhYrehxin3NStELsSKCT4K2 GdnSyH3YtwcxFvQrVVJMm1JhTS4QVX7MFsX56uJLUfiZ DE1bawNcRJB9rVm3buyMVfr8mBEoyyu73NBovf2oXJsJ CakcnaRDHka2gXyfbEd2d3xsvkJkqsLw2akB3zsN1D2S)

VALIDATOR_IDENTITIES=(HiMfCsAvNr5KDaAC4RxzbGtV6TcpeqeTjgNFjCeTHMSw EAqg3S1tHxCmQbwKXFLXBvsWx2Yvh2jyFCqFx5C1s7PM 75Mv8XfC4VxRV7XJ8Ev4DeiJfa2FdbKrAYNc6TUinvkR)

RPC_URL=http://localhost:8899/

args=(
  --url "$RPC_URL" \
  --monitor-active-stake \
  --no-duplicate-notifications \
)

for tv in "${VALIDATOR_IDENTITIES[@]}"; do
  args+=(--validator-identity "$tv")
done

if [[ -n $TRANSACTION_NOTIFIER_SLACK_WEBHOOK ]]; then
  args+=(--notify-on-transactions)
fi

exec solana-watchtower "${args[@]}"
