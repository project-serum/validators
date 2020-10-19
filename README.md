# Validators
## Motivation
This repository is meant to serve as an example for how to run a solana validator.
It does not give specifics on the architecture of Solana, and should not be used as a substitute for Solana's documentation.
It is highly recommended to read [Solana's Documentation](https://docs.solana.com/running-validator) about running a validator. 
This repository should be used in conjunction with Solana's guide. It provides practical
real-world examples of cluster setup, and should act as a starting point for participating
in mainnet validation. 

This repository gives two examples of potential validator setups. The first is a 
single node validator that can be used as an entry point for querying on-chain Solana data, or
validating transactions. 
The second is a cluster of Solana validators that are load balanced by an nginx server. Nginx
has an active health check feature offered in their premium version. A configuration
for active health checks is also included.

The end goal of this guide is to have a solana validator cluster running in a cloud 
environment.
 
## Overview of setups
- run a single validator
- run a cluster of validators
## Running a single validator
#### Instance configuration
##### Choosing an instance type
Solana's documentation recommends choosing a node type with the highest number of cores possible ([see here](https://docs.solana.com/running-validator/validator-reqs)).
Additionally the Solana mainnet utilizes GPUs to increase network throughput. Solana's documentation
recommends using Nvidia Turing or Volta family GPUs which are available through most cloud providers. 

This guide was tested using [Amazon AWS g4dn.16xlarge instances](https://aws.amazon.com/ec2/instance-types/g4/) using the
Ubuntu 18.04 Deep Learning AMI. These instances provide Nvidia T4 GPUs with a balance of high network
throughput and CPU resources.

##### Instance network configuration
After provisioning an instance it is important to configure network whitelists to be compatible
with a validator's network usage. Solana nodes communicate via a gossip protocol. This protocol takes
place over a port range specified upon validator startup. For this guide we will set that port range to 
8000-8012. Be sure to whitelist network traffic on whichever port range you choose.

Validator RPC servers also bind to configurable ports. This guide will set RPC servers to use port 8899
for standard HTTP requests and 8900 for websocket connections.

#### Setting up a single validator
Once an instance has been deployed and is accessible over SSH, we can use ansible to run some basic setup 
scripts. Ansible works by inspecting the contents of a `hosts.yaml` file, which defines the inventory of servers to which one can deploy.
To make our servers accesible to ansible, add your server's network location to the validators block in `deploy/hosts.yaml`. 
This will indicate that the specified server is part of the `validators` group, which will contain our validator machines.
`deploy/setup.yaml` contains a set of common setup steps for configuring a server from the base OS image. You can run these 
setup steps using  
```
# run this from the /deploy directory
ansible-playbook -i hosts.yaml -l validators setup.yaml
```

## Running a cluster of validators
