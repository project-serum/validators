#!/bin/bash -e

pssh=$(which parallel-ssh || which pssh)

$pssh -h <(ansible all --list-hosts -i hosts.yaml | tail -n+2) -l ubuntu -P -t0 'sudo tail -n0 -qF /var/log/supervisor/*.log'
