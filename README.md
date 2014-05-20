## researchcompendia-deployment

This repo contains fabric deployment files.

### Prerequisits

* Get an environment file from me 
* Be able to run `vagrant up`

### Procedures

#### provisioning 

A vagrant example

* `git clone https://github.com/researchcompendia/researchcompendia-deployment.git`
* `cd researchcompendia-deployment`
* `vagrant up`
* `fab vagrant provision` 

Provision is not idempotent, so running it twice will probably fail in interesting ways.
If you want to start over need to run `vagrant destroy` first.

#### deployment

* `fab dev deploy`, can also use `vagrant`, `staging`, `prod`

### Plans

I may drop all of this for Ansible.
