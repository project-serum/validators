#!/bin/bash -e

pssh=$(which parallel-ssh || which pssh)

$pssh -h <(ansible all --list-hosts -i hosts.yaml | tail -n+2) -i -l ubuntu -- 'curl http://localhost:8899/health'
