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
* run `fab setup` 

Rerunning setup? No, if you want to do that you need to `vagrant destroy` first
and start over.

### Plans

I am new to fabric and new to vagrant. Here are my tentative plans:

* Refactor or dramatically change things while I learn better practices.
* get the script running with any host, not just a vagrant box.
* make `setup` sync expected state versus scratch.
* `test`
* `deploy` (does the work to deploy a new version of the site)
* `release` (does work to package a new release, which right now means we merge develop to master and create a new tag)

