## researchcompendia-deployment

This repo contains work to develop fab files to automate configuration
and deployment.

Currently, the fab file only supports running setup on a clean vagrant
box that is running. The first step I took was to convert a bootstrap
shell script to a fabric file, and that's all my bootstrap script did.

### Prerequisits

* Get an env directory from me.
* Be able to run `vagrant up`

### Procedure

* check out the repo
* navigate to the repo directory
* get the vagrant box up and running
* run `fab vagrant provision` 

Rerunning provision? Probably not, if you want to do that you need to `vagrant destroy` first
and start over.

* run `fab dev deploy`, can also use vagrant, staging, prod

### Plans

I am new to fabric and new to vagrant. Here are my tentative plans:

* Refactor or dramatically change things while I learn better practices.
* get the script running with any host, not just a vagrant box.
* make `provision` sync expected state versus scratch.
* `deploy` (does the work to deploy a new version of the site)
