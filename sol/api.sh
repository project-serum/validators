#!/usr/bin/env bash
set -ex

#shellcheck source=/dev/null
#. ~/service-env.sh
PATH=/home/sol/.local/share/solana/install/active_release/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin

# Parameters from https://docs.solana.com/clusters#mainnet-beta
ENTRYPOINT=mainnet-beta.solana.com:8001
TRUSTED_VALIDATOR_PUBKEYS=(7Np41oeYqPefeNQEHSv1UDhYrehxin3NStELsSKCT4K2 GdnSyH3YtwcxFvQrVVJMm1JhTS4QVX7MFsX56uJLUfiZ DE1bawNcRJB9rVm3buyMVfr8mBEoyyu73NBovf2oXJsJ CakcnaRDHka2gXyfbEd2d3xsvkJkqsLw2akB3zsN1D2S)
EXPECTED_BANK_HASH=Fi4p8z3AkfsuGXZzQ4TD28N8QDNSWC7ccqAqTs2GPdPu
EXPECTED_GENESIS_HASH=5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d
EXPECTED_SHRED_VERSION=13490

# Delete any zero-length snapshots that can cause validator startup to fail
find /data/sol/ledger/snapshot-* -size 0 -print -exec rm {} \; || true


identity_keypair=~/api-identity.json

if [[ -f $identity_keypair ]]; then
  echo 'identity_keypair exists'
else
  echo 'generating identity_keypair'
  solana-keygen new -o $identity_keypair --no-passphrase
fi

identity_pubkey=$(solana-keygen pubkey $identity_keypair)

trusted_validators=()
for tv in "${TRUSTED_VALIDATOR_PUBKEYS[@]}"; do
  [[ $tv = "$identity_pubkey" ]] || trusted_validators+=(--trusted-validator "$tv")
done

if [[ -n "$EXPECTED_BANK_HASH" ]]; then
  maybe_expected_bank_hash="--expected-bank-hash $EXPECTED_BANK_HASH"
fi

args=(
  --gossip-port 8001
  --dynamic-port-range 8002-8012
  --entrypoint "${ENTRYPOINT}"
  --ledger /data/sol/ledger
  --accounts /mnt/accounts
  --identity "$identity_keypair"
  --enable-rpc-transaction-history
  --limit-ledger-size 50000000
  --health-check-slot-distance 500
  --cuda
  --rpc-port 8899
  --private-rpc
  --expected-genesis-hash "$EXPECTED_GENESIS_HASH"
  --expected-shred-version "$EXPECTED_SHRED_VERSION"
  ${maybe_expected_bank_hash}
  "${trusted_validators[@]}"
  --no-untrusted-rpc
  --no-voting
  --log -
  --wal-recovery-mode skip_any_corrupted_record
)

# Note: can get into a bad state that requires actually fetching a new snapshot. One such error that indicates this:
# "...processing for bank 0 must succeed: FailedToLoadEntries(InvalidShredData(Custom(\"could not reconstruct entries\")))"
if [[ -d /data/sol/ledger ]]; then
  args+=(--no-snapshot-fetch)
fi

exec solana-validator "${args[@]}"
