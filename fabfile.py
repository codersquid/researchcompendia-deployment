import string, random
from os.path import join
from fabric.api import task, env, cd, sudo, local
from fabric.contrib.files import sed, upload_template
from fabtools import require, supervisor
import fabtools

env.disable_known_hosts = True
env.user = 'vagrant'
env.hosts = ['127.0.0.1:2222']
result = local('vagrant ssh-config | grep IdentityFile | cut -f4 -d " "', capture=True)
env.key_filename = result

SITE_USER = 'tyler'
SITE_REPO = 'git://github.com/researchcompendia/researchcompendia.git'
SITE_VERSION = local('cat SITE_VERSION', capture=True)
SITE_ENVIRONMENT = 'vagrant'


@task
def setup():

    install_dependencies()

    lockdowns()

    setup_database()

    setup_user()

    setup_site()
 
    setup_nginx()

    setup_supervisor()

    setup_rabbitmq()

    ## collectd
    # install, files, restart
    #setup_collectd()

    ## statsite
    #setup_statsite()

    ## papertrail
    #setup_papertrail()
    # site/logs/papertrail.yml
    # change rsyslog file
    # restart rsyslog
    # rvm install with ruby
    # gem install remote_syslog
    # wrap remote_syslog
    # supervisor file
    # restart supervisor


def setup_rabbitmq():
    secret = randomstring(64)
    sudo('rabbitmqctl delete_user guest')
    sudo('rabbitmqctl add_user tyler "%s"' % secret)
    sudo('rabbitmqctl set_permissions -p / tyler ".*" ".*" ".*"')
    upload_template('templates/DJANGO_BROKER_URL', '/home/tyler/site/env/DJANGO_BROKER_URL',
            use_jinja=True, context={'password': secret}, use_sudo=True)
    sudo('chown tyler:tyler /home/tyler/site/env/DJANGO_BROKER_URL')

def setup_nginx():
    upload_template('templates/researchcompendia_nginx', '/etc/nginx/sites-available/researchcompendia', use_sudo=True)
    # figure out how to do the status conf
    require.nginx.enabled('researchcompendia')

def setup_supervisor():
    upload_template('templates/researchcompendia_web.conf', '/etc/supervisor/conf.d/researchcompendia_web.conf', use_sudo=True)
    upload_template('templates/celeryd.conf', '/etc/supervisor/conf.d/celeryd.conf', use_sudo=True)
    supervisor.update_config()

def lockdowns():
    # don't share nginx version in header and error pages
    sed('/etc/nginx/nginx.conf', '# server_tokens off;', 'server_tokens off;', use_sudo=True)
    # require keyfile authentication
    sed('/etc/ssh/sshd_config', '^#PasswordAuthentication yes', 'PasswordAuthentication no', use_sudo=True)

def su(cmd, user):
    sudo("su %s -c '%s'" % (user, cmd))

def vsu(cmd, workon=None, user=None):
    if workon is None:
        workon = SITE_VERSION
    if user is None:
        user = SITE_USER
    sudo("su %s -c 'source ~/.bash_aliases; workon %s; %s'" % (user, workon, cmd))


def setup_site():
    su('source ~/.bash_aliases; mkvirtualenv %s' % SITE_VERSION, user=SITE_USER)
    home = fabtools.user.home_directory(SITE_USER)
    envdir = join(home, 'site', 'env')
    djangodir = join(home, 'site', 'tyler', 'companionpages')
    with cd(join(home, 'site', 'tyler')):
        vsu('pip install -r requirements/production.txt')
    with cd(djangodir):
        vsu('envdir %s ./manage.py syncdb --noinput --migrate' % envdir)
        vsu('envdir %s ./manage.py loaddata fixtures/sites.json' % envdir)
        vsu('envdir %s ./manage.py loaddata fixtures/home.json' % envdir)


def setup_database():
    require.postgres.server()
    su('createuser -S -D -R -w %s' % SITE_USER, 'postgres')
    su('createdb -w -O %s %s' % (SITE_USER, SITE_USER), 'postgres')


def setup_user():
    sudo('useradd -s/bin/bash -d/home/%s -m %s' % (SITE_USER, SITE_USER))
    home = fabtools.user.home_directory(SITE_USER)
    with cd(home):
        su('mkdir venvs site', SITE_USER)
        su('cp /vagrant/templates/_bash_aliases .bash_aliases', SITE_USER)
    with cd(join(home, 'site')):
        # make directories
        su('mkdir logs bin env bin/runnerenv', SITE_USER)
        # add site files
        su('cp /vagrant/templates/runserver.sh bin/', SITE_USER)
        su('cp /vagrant/templates/celeryworker.sh bin/', SITE_USER)
        su('cp /vagrant/templates/check_downloads.sh bin/', SITE_USER)
        su('cp /vagrant/SITE_VERSION bin/runnerenv/', SITE_USER)
        su('cp %s env/' % join('/vagrant/env', SITE_ENVIRONMENT, '*'), SITE_USER)
        su('git clone %s tyler' % SITE_REPO, SITE_USER)


def install_dependencies():
    add_apt_sources()
    require.deb.uptodate_index(max_age={'hour': 1})
    install_debian_packages()
    install_python_packages()


def add_apt_sources():
    fabtools.deb.add_apt_key(url='http://www.rabbitmq.com/rabbitmq-signing-key-public.asc')
    require.deb.source('rabbitmq-server', 'http://www.rabbitmq.com/debian/', 'testing', 'main')
    require.deb.uptodate_index(max_age={'hour': 1})


def install_debian_packages():
    fabtools.deb.add_apt_key(url='http://www.rabbitmq.com/rabbitmq-signing-key-public.asc')
    require.deb.source('rabbitmq-server', 'http://www.rabbitmq.com/debian/', 'testing', 'main')
    require.deb.uptodate_index(max_age={'hour': 1})

    # os packages
    require.deb.packages([
        'python-software-properties',
        'python-dev',
        'build-essential',
        #'python-pip',
        'nginx',
        'libxslt1-dev',
        'supervisor',
        'git',
        'tig',
        'postgresql',
        'postgresql-server-dev-9.1',
        'memcached',
        'vim-nox',
        'exuberant-ctags',
        'multitail',
        'curl',
        'tmux',
        'htop',
        'memcached',
        'libmemcached-dev',
        'ack-grep',
        'rabbitmq-server',
    ])


def install_python_packages():

    sudo('wget https://bitbucket.org/pypa/setuptools/raw/bootstrap/ez_setup.py')
    sudo('wget https://raw.github.com/pypa/pip/master/contrib/get-pip.py')
    sudo('python ez_setup.py')
    sudo('python get-pip.py')

    # install global python packages
    require.python.packages([
        'virtualenvwrapper',
        'setproctitle',
        'envdir',
    ], use_sudo=True)


def randomstring(n):
    return ''.join(random.choice(string.ascii_letters + string.digits + '~@#%^&*-_') for x in range(n))
