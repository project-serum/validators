# Validators
## Motivation
This repository is meant to serve as an example for how to run a solana validator. It does not give specifics on the 
architecture of Solana, and should not be used as a substitute for Solana's documentation. It is highly recommended to 
read [Solana's Documentation](https://docs.solana.com/running-validator) on running a validator. This repository 
should be used in conjunction with Solana's guide. It provides practical real-world examples of a cluster setup, and 
should act as a starting point for participating in mainnet validation. 

This repository gives two examples of potential validator setups. The first is a single node validator that can be used 
as an entry point for querying on-chain Solana data, or validating transactions. The second is a cluster of Solana 
validators that are load balanced by an NGINX server. NGINX has an active health check feature offered in their premium 
version. A load balancer configuration using the active health checks feature is also included.

The end goal of this guide is to have a solana validator cluster running in a cloud environment.
 
## Running a single validator
#### Choosing an instance type
Solana's documentation recommends choosing a node type with the highest number of cores available and a CUDA enabled GPU 
([see here](https://docs.solana.com/running-validator/validator-reqs)). Solana uses GPUs to increase throughput and 
the documentation recommends using Nvidia Turing or Volta family GPUs which are available through most cloud providers. 

This guide was tested using [Amazon AWS g4dn.xlarge instances](https://aws.amazon.com/ec2/instance-types/g4/) with 
the Ubuntu 18.04 Deep Learning AMI. g4dn.xlarge istances come with Nvidia T4 GPUs which have a balance of high network 
throughput and CPU resources. Additionally the Deep Learning AMI comes preinstalled with CUDA which is required by 
Solana.

The Solana ledger is stored on disk. As of this writing, specifying the minimum required ledger length uses roughly 
200GiB of disk space. When provisioning your instance, you should choose a disk size of at least 200GiB to ensure 
sufficient space for the ledger.

#### Instance network configuration
After provisioning an instance, it is important to configure network whitelists to be compatible with a validator's 
network usage. Solana nodes communicate via a gossip protocol on a port range that is specified upon validator startup. 
For this guide we will set that port range to 8000-8012 (see `sol/api.sh`). Be sure to whitelist all network traffic on 
whichever port range you choose. Validator RPC servers also bind to configurable ports. This guide will set RPC servers
to use port 8899 for standard REST requests and 8900 for websocket connections (also defined in `sol/api.sh`).

#### Setting up a single validator
Once an instance has been deployed and is accessible over SSH, we can use ansible to run the validator setup script. 
Ansible works by inspecting the contents of the `hosts.yaml` file, which defines the inventory of servers. To make our 
servers accesible to Ansible, add your server's url or ip address to the validators block in `deploy/hosts.yaml`. 
This adds the specified server to the `validators` group, which describes our inventory of validator machines. 

Ansible will need access to the `sol` user over ssh, which can be done by adding an ssh key to the 
`sol` user's `~/.ssh/authorized_keys` file. Our ansible setup script takes care of this by copying the 
`authorized_keys` file in `deploy/authorized_keys` to the `sol` user's `authorized_keys` file. Be sure to add any ssh 
keys that need deploy permissions to that file prior to running the setup script.

`deploy/setup.yaml` contains a set of common setup steps for configuring a validator from the base OS image. You 
can run these setup steps using:

```
$ # run this from the /deploy directory
$ ansible-playbook -i hosts.yaml -l validators setup.yaml
```

Among other things, the above command will modify your new instance by
- creating and configure the `sol` user
- installing the contents of `deploy/etc/common` and `deploy/etc/validator` to the `/etc` directory on the validator
- increasing the memory mapped file limit ([see here](https://docs.solana.com/running-validator/validator-start#manual))
- increasing the UDP buffer size ([see here](https://docs.solana.com/running-validator/validator-start#manual))
- increasing dns cache size (see `deploy/common/dnsmasq.d/local.conf`)
- caching negative dns replies even if they don't have a ttl (see `deploy/common/dnsmasq.d/local.conf`)
- creating a basic NGINX config at `/etc/nginx`
- setting up supervisor and running the `deploy/validator.conf` configuration
- installing NGINX sites located at `deploy/etc/validator/nginx/sites-available/validator.conf`
- installing code from this repository
- installing the Solana CLI
- increasing the file descriptor limit for processes managed by supervisor to 600000
- creating a `tmpfs` device for the accounts store mounted at `/mnt/accounts`

After running the `setup.yaml` script, a reboot is necessary to pick up various system configs. If it is the first time
that the validator starts, it is possible that it thinks that a local ledger is present when there is not: commenting out the
lines 64-66 of `deploy/api.sh` will prevent this. Post-reboot, supervisor should start up the validator using the
`sol/api.sh` script. The validator will be listening on port 8899 for rest requests, so issuing a curl to the `/health`
path will return the health status of the validator.
```
$ curl http://localhost:8899
``` 

This curl will likely return the status `behind`, as the validator is catching up with the existing cluster. Once the 
validator has successfully caught up, it will be ready to serve RPC requests on port `8899`

#### A note about the accounts store
The accounts store is a portion of the Solana state model that requires high throughput access for validators to 
function properly. One method for achieving higher throughput is by keeping the accounts store in memory rather than
on disk. A straightforward way to do this is by using a `tmpfs` block device. For the uninitiated, `tmpfs` is a 
temporary file storage system in Unix that emulates a filesystem, with the data actually being store in 
memory. Keeping the accounts store in memory allow for quicker accesses, and significantly reduces latency for 
expensive account operations.

#### TL;DR
- deploy a cloud instance with an NVIDIA GPU with CUDA enabled
- choose a disk size greater than 200 GiB
- Whitelist all internet traffic on ports `8000-8012`
- add your ssh key to `deploy/authorized_keys`
- add your server's URL or IP address to the validators block of `deploy/hosts.yaml`
- run `ansible-playbook -i hosts.yaml -l validators setup.yaml` from your local terminal 
- ssh into the new machine and reboot to pick up system config changes 
- check that the new validator is running with `curl http://localhost:8899` 

## Running a cluster of validators
Running a cluster of validators allows for load balancing RPC requests across many machines. Using this repo's setup, 
each validator in the cluster can act as a standalone validator and will respond to RPC requests over port 8899. The 
cluster is composed of many validators with an NGINX load balancer directing traffic. 

#### Adding nodes 
To add a node to the cluster, initialize an instance as we did in the first section. After running the `setup.yaml` 
script and rebooting the instance the new validator should be in a state where it is responding to querys on its RPC 
port. 

#### Adding a load balancer
At this point, we need to add a third machine which will act as the load balancer, sitting in front of the solana validators and directing
traffic to the cluster. The load balancer machine will only be used for proxying traffic to upstream validators so 
there is no need to choose a GPU instance as we did for the validators. A general purpose compute instance is likely 
sufficient (e.g. a good choice might be an [AWS m5 instance](https://aws.amazon.com/ec2/instance-types/m5/)). 

The load balancer setup in this repo uses an NGINX reverse proxy. NGINX plus (their premium version) includes an active
health checks feature which is useful for maintaining a healthy cluster. A common failure pattern is for
RPC requests to overload compute resources on a validator, which causes the validator to fall behind. This will lead to 
client issues. Reads directed at the lagging node will be delayed and writes will fail due to expired transaction 
signatures. NGINX active health checks provide a mechanism for directing traffic away from a lagging node, which allows the
node to recover. Once the node starts passing the health check, NGINX will add the node back into the set of load
balanced machines. It is highly recommended to use the active health checks if your application requires high uptime.

If your validators are located in AWS, one easy way to provision NGINX plus is through the 
[NGINX Plus Ubuntu AMI](https://aws.amazon.com/marketplace/pp/Nginx-Software-Inc-NGINX-Plus-Ubuntu-AMI/B00DIF4A6Y).
This AMI comes preinstalled with NGINX plus and removes some manual setup involved in licensing. If you choose not to 
use active health checks, a standard Ubuntu LTS image will suffice.

#### Configure NGINX
To setup the reverse proxy, we need to specify the upstream servers to which NGINX should proxy incoming requests. The 
NGINX config works by importing NGINX configurations that are defined in `deploy/etc/lb/nginx/sites-available` to form
a global configuration. NGINX includes all configuration files located in the `/etc/nginx/sites-enabled` directory. To 
enable a site, Ansible creates a symbolic link from the `/etc/nginx/sites-available` directory to 
`/etc/nginx/sites-enabled`. Ansible will create such a link for any site that is listed in the `nginx_sites` entry of the 
`deploy/hosts.yaml` for a particular server. 

To add servers to the set of upstreams, modify the two upstream blocks of 
`deploy/etc/lb/nginx/sites-available/validator.conf` as follows:
```
...
upstream validator_backend {
    least_conn;
    keepalive 8192;
    
    // Delete these
    server validator-1.test.net:8899 max_fails=20 fail_timeout=2;
    server validator-2.test.net:8899 max_fails=20 fail_timeout=2;
    
    // add new servers here at port 8899 for REST connections
}

upstream validator_ws_backend {
    least_conn;

    // Delete these
    server validator-1.test.net:8900 max_fails=20 fail_timeout=2;
    server validator-2.test.net:8900 max_fails=20 fail_timeout=2;
    
    // add new servers here at port 8900 for websocket connections
}
...
``` 

You will also need to replace the `validator-lb.test.net` in the `server_name` directive with the URL you will be using 
to access this server. Once these steps are completed HTTP access on port 80 will be properly
configured. To add HTTPS support, modify the certificate files at `deploy/etc/lb/ssl` to include your HTTPS certificates
and change the lines of `validator.conf` starting with `ssl_` to point to your new certificate files.

HTTPS certificates can be obtained through any certificate authority. One such CA is 
[Let's Encrypt](https://letsencrypt.org/getting-started/). Alternatively if you are routing traffic through Cloudflare to 
prevent DDOS attacks, Cloudflare provides SSL certificates. If you are running validators behind a firewall and are not 
concerned with SSL, you can comment out the entire NGINX server listening on port 443. 

#### Deploying to the load balancer
Once the load balancer machine is provisioned and NGINX is configured, add the URL or IP address of the new machines
to the `deploy/hosts.yaml` file in the `load_balancers` group. An example load balancer for each setup is provided. 
If you are using NGINX plus, use the `validator-lb-health-checks.test.net` setup, otherwise use the 
`validator-lb-standard.test.net` setup. Note that if you are using the NGINX plus AMI it is important not to include 
`nginx` in the `extra_packages` list in `hosts.yaml`. Deploy to the load balancer machine using
```
# from the deploy/directory
$ ansible-playbook -i hosts.yaml -l load_balancers setup.yaml 
```

After the deploy it might be necessary to restart NGINX on the load balancer machine. 

#### Cluster monitoring
One advantage of using NGINX plus is the monitoring dashboard that is included. With Active health checks enabled 
the NGINX dashboard served at port 30000 gives an overview of hosts that are failing the health check.

Active health checks work by pinging a flask server on port 9090. This server checks the block height of the local
validator against that of Solana mainnet validators. If the local validator is more than 15 blocks behind (this is 
configurable by changing `sol/data/unhealthy_block_threshold`) the validator will respond with a 500. NGINX marks 
servers responding with an error code in the 5xx range as unhealthy, and will avoid routing traffic to unhealthy nodes.
 
#### TL;DR
- setup validator nodes following part one of this guide
- add URLs for those nodes to the NGINX config
- setup a load balancer machine which will run an NGINX reverse proxy load balancer
- modify the NGINX template configs in `deploy/etc/lb/nginx/sites-available/`. Use `validator.conf` if you are 
using standard open source NGINX, and `validator-health-checks.conf` if you are using NGINX plus
- add SSL certificates to `deploy/etc/lb/ssl` 
- deploy to the load balancer machine using `ansible-playbook -i hosts.yaml -l load_balancers setup.yaml` 
