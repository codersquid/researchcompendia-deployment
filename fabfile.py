"""Deployment scripts for ResearchCompendia
with credit to Scipy-2014 fabric.py

fab <dev|staging|prod|vagrant> <deploy|provision>[:<git ref>]

deploy: deploys the site to the specified environment. If no git ref is provided, deploys HEAD
provision: provisions a box to run the site. is not idempotent. do not rerun.
git ref: a git branch, hash, tag


Example usages:
$ fab staging deploy
$ fab prod deploy:1.0.1-b7

"""
import datetime, string, random, re
from os.path import join, dirname, abspath
import fabric.api
from fabric.api import run, task, env, cd, sudo, local, put
from fabric.contrib.files import sed, append
from fabtools import require, supervisor, postgres, deb, files
from fabtools.files import upload_template
from fabtools.user import home_directory
import fabtools

env.disable_known_hosts = True

SITE_USER = 'tyler'
SITE_GROUP = 'tyler'
SITE_NAME = 'tyler'
SITE_REPO = 'git://github.com/researchcompendia/researchcompendia.git'
FAB_HOME = dirname(abspath(__file__))
TEMPLATE_DIR = join(FAB_HOME, 'templates')

@task
def dev():
    env.update({
        'carbon': '10.176.162.45',
        'site': 'dev.codersquid.com',
        'available': 'researchcompendia',
        'hosts': ['dev.codersquid.com'],
        'site_environment': 'dev_environment.sh',
    })


@task
def staging():
    env.update({
        'carbon': '10.176.162.45',
        'site': 'labs.researchcompendia.org',
        'available': 'researchcompendia',
        'hosts': ['labs.researchcompendia.org'],
        'site_environment': 'staging_environment.sh',
    })


@task
def prod():
    env.update({
        'carbon': '10.176.162.45',
        'site': 'researchcompendia.org',
        'available': 'researchcompendia',
        'hosts': ['researchcompendia.org'],
        'site_environment': 'prod_environment.sh',
    })


@task
def vagrant():
    env.update({
        'carbon': '10.176.162.45',
        'user': 'vagrant',
        'site': '127.0.0.1:2222',
        'available': 'researchcompendia',
        'hosts': ['127.0.0.1:2222'],
        'site_environment': 'dev_environment.sh',
        'key_filename': local('vagrant ssh-config | grep IdentityFile | cut -f4 -d " "', capture=True),
    })


@task
def uname():
    """the hello world of fabric
    """
    fabric.api.require('site', 'available', 'hosts', 'site_environment',
        provided_by=('dev', 'staging', 'prod', 'vagrant'))
    run('uname -a')

@task
def deploy(version_tag=None):
    """deploys a new version of the site

    version_tag: a git tag, defaults to HEAD
    """
    fabric.api.require('site', 'available', 'hosts', 'site_environment',
        provided_by=('dev', 'staging', 'prod', 'vagrant'))

    maintenance_enable()
    supervisor.stop_process(SITE_NAME)
    supervisor.stop_process('celery')

    new_env = virtualenv_name(commit=version_tag)
    mkvirtualenv(new_env)
    setup_site_root()
    update_site_version(new_env)
    update_repo(commit=version_tag)
    install_site_requirements(new_env)
    collectstatic()

    supervisor.start_process(SITE_NAME)
    supervisor.start_process('celery')
    maintenance_disable()


@task
def provision(version_tag=None):
    """Run only once to provision a new host.
    This is not idempotent. Only run once!
    """
    fabric.api.require('site', 'available', 'hosts', 'site_environment',
        provided_by=('dev', 'staging', 'prod', 'vagrant'))
    install_dependencies()
    lockdown_nginx()
    lockdown_ssh()
    setup_database()
    setup_site_user()
    setup_site_root()
    setup_envvars()
    add_download_checker()
    update_repo(version_tag)
    setup_django(version_tag)
    setup_nginx()
    setup_supervisor()
    setup_rabbitmq()
    setup_collectd()

    # statsite
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



def setup_collectd():
    hostname = run('hostname')
    upload_template('collectd.conf', '/etc/collectd/collectd.conf', use_jinja=True,
        context={'carbonhost': env.carbon, 'hostname': hostname},
        template_dir=TEMPLATE_DIR, use_sudo=True)
    sudo('/etc/init.d/collectd restart')

def setup_rabbitmq(user=None):
    if user is None:
        user = SITE_USER

    envfile = join(home_directory(SITE_USER), 'site/bin/environment.sh')
    secret = randomstring(64)
    sudo('rabbitmqctl delete_user guest')
    sudo('rabbitmqctl add_user %s "%s"' % (user, secret))
    sudo('rabbitmqctl set_permissions -p / %s ".*" ".*" ".*"' % user)
    amqp_url = 'amqp://%s:%s@localhost:5672//' % (SITE_USER, secret)
    sed(envfile, 'DJANGO_BROKER_URL=".*"', 'DJANGO_BROKER_URL="%s"' % amqp_url, use_sudo=True)



def setup_nginx():
    site_root = join(home_directory(SITE_USER), 'site')
    upload_template('maintenance_nginx', '/etc/nginx/sites-available/maintenance',
        use_sudo=True, template_dir=TEMPLATE_DIR)
    upload_template('maintenance_index.html', '/usr/share/nginx/www/index.html',
        use_sudo=True, template_dir=TEMPLATE_DIR)
    upload_template('researchcompendia_nginx',
        '/etc/nginx/sites-available/researchcompendia',
        context={
            'server_name': env.site,
            'access_log': join(site_root, 'logs', 'access.log'),
            'error_log': join(site_root, 'logs', 'error.log'),
            'static_location': join(site_root, 'static'),
            'media_location': join(site_root, 'media'),
        },
        use_jinja=True, use_sudo=True, template_dir=TEMPLATE_DIR)
    require.nginx.enabled('researchcompendia')

def setup_supervisor():
    site_root = join(home_directory(SITE_USER), 'site')
    upload_template('researchcompendia.conf', 
        '/etc/supervisor/conf.d/researchcompendia_web.conf',
        context={
            'command': join(site_root, 'bin', 'runserver.sh'),
            'user': SITE_USER,
            'group': SITE_GROUP,
            'logfile': join(site_root, 'logs', 'gunicorn_supervisor.log'),

        },
        use_jinja=True, use_sudo=True, template_dir=TEMPLATE_DIR)
    upload_template('celeryd.conf', 
        '/etc/supervisor/conf.d/celeryd.conf',
        context={
            'command': join(site_root, 'bin', 'celeryworker.sh'),
            'user': SITE_USER,
            'group': SITE_GROUP,
            'logfile': join(site_root, 'logs', 'celery_worker.log'),

        },
        use_jinja=True, use_sudo=True, template_dir=TEMPLATE_DIR)
    supervisor.update_config()


def lockdown_nginx():
    # don't share nginx version in header and error pages
    sed('/etc/nginx/nginx.conf', '# server_tokens off;', 'server_tokens off;', use_sudo=True)
    sudo('service nginx restart')

def lockdown_ssh():
    sed('/etc/ssh/sshd_config', '^#PasswordAuthentication yes', 'PasswordAuthentication no', use_sudo=True)
    append('/etc/ssh/sshd_config', ['UseDNS no', 'PermitRootLogin no', 'DebianBanner no', 'TcpKeepAlive yes'], use_sudo=True)
    sudo('service ssh restart')

def setup_django(version_tag):
    virtualenv = virtualenv_name(commit=version_tag)
    mkvirtualenv(virtualenv)
    update_site_version(virtualenv)
    install_site_requirements(virtualenv)
    collectstatic()
    migrate_and_load_database()


def migrate_and_load_database():
    environment = join(home_directory(SITE_USER), 'site/bin/environment.sh')
    djangodir = join(home_directory(SITE_USER), 'site', SITE_NAME, 'companionpages')
    with cd(djangodir):
        vsu('source %s; ./manage.py syncdb --noinput --migrate' % environment)
        vsu('source %s; ./manage.py loaddata fixtures/*' % environment)


def install_site_requirements(virtualenv):
    home = home_directory(SITE_USER)
    with cd(join(home, 'site', SITE_NAME)):
        vsu('pip install -r requirements/production.txt', virtualenv=virtualenv)


def setup_database():
    require.postgres.server()
    # NOTE: fabtools.require.postgres.user did not allow me to create a user with no pw prompt?
    if not postgres.user_exists(SITE_USER):
        su('createuser -S -D -R -w %s' % SITE_USER, 'postgres')
    if not postgres.database_exists(SITE_USER):
        require.postgres.database(SITE_USER, SITE_USER, encoding='UTF8', locale='en_US.UTF-8')
    # change default port
    # port = 5432
    # /etc/postgresql/9.1/main/postgresql.conf


def setup_site_user():
    if not fabtools.user.exists(SITE_USER):
        sudo('useradd -s/bin/bash -d/home/%s -m %s' % (SITE_USER, SITE_USER))


def setup_envvars():
    env_template_dir = join(FAB_HOME, 'env')
    secret = randomstring(64)
    site_root = join(home_directory(SITE_USER), 'site')
    bindir = join(site_root, 'bin')
    static_root = join(site_root, 'static')
    media_root = join(site_root, 'media')
    destination_envfile = join(bindir, 'environment.sh')

    with cd(bindir):
        upload_template(env.site_environment, destination_envfile,
            context={
                'secret_key': secret,
                'static_root': static_root,
                'media_root': media_root,
            },
            template_dir=env_template_dir,
            use_jinja=True, use_sudo=True, chown=True, user=SITE_USER)


def setup_site_root():
    site_root = join(home_directory(SITE_USER), 'site')
    bindir = join(site_root, 'bin')

    with cd(home_directory(SITE_USER)):
        su('mkdir -p venvs site')

    with cd(site_root):
        su('mkdir -p logs bin env media static')
        put(template_path('runserver.sh'), bindir, use_sudo=True)
        put(template_path('celeryworker.sh'), bindir, use_sudo=True)
        put(template_path('check_downloads.sh'), bindir, use_sudo=True)
        sudo('chown -R %s:%s %s' % (SITE_USER, SITE_USER, site_root))

    with cd(bindir):
        su('chmod +x runserver.sh celeryworker.sh check_downloads.sh')

def add_download_checker():
    site_root = join(home_directory(SITE_USER), 'site')
    bindir = join(site_root, 'bin')
    job = join(home_directory(SITE_USER), 'check_downloads')
    upload_template('check_downloads', job,
        context={
            'command': join(bindir, 'check_downloads.sh'),
            'logfile': join(site_root, 'logs', 'cron_checkdownloads.log'),
        },
        use_jinja=True, use_sudo=True, template_dir=TEMPLATE_DIR)
    sudo('chown %s:%s %s' % (SITE_USER, SITE_USER, job))
    su('crontab %s' % job)


def update_dependencies():
    require.deb.uptodate_index(max_age={'hour': 1})
    install_debian_packages()
    install_python_packages()


def install_dependencies():
    add_apt_sources()
    install_debian_packages()
    install_python_packages()


def add_apt_sources():
    deb.add_apt_key(url='http://www.rabbitmq.com/rabbitmq-signing-key-public.asc')
    require.deb.source('rabbitmq-server', 'http://www.rabbitmq.com/debian/', 'testing', 'main')
    require.deb.uptodate_index(max_age={'hour': 1})


def install_debian_packages():

    # os packages
    require.deb.packages([
        'python-software-properties',
        'python-dev',
        'build-essential',
        #'python-pip',
        'nginx-extras',
        'libxslt1-dev',
        'supervisor',
        'git',
        'tig',
        'postgresql',
        'postgresql-server-dev-9.1',
        'memcached',
        'vim',
        'exuberant-ctags',
        'multitail',
        'curl',
        'tmux',
        'htop',
        'memcached',
        'libmemcached-dev',
        'ack-grep',
        'rabbitmq-server',
        'collectd',
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
    ], use_sudo=True)


def su(cmd, user=None):
    if user is None:
        user = SITE_USER
    sudo("su %s -c '%s'" % (user, cmd))


def vsu(cmd, virtualenv=None, user=None):
    if virtualenv is None:
        virtualenv = get_site_version()
    if user is None:
        user = SITE_USER
    home = home_directory(user)
    venvdir = join(home, 'venvs', virtualenv, 'bin/activate')
    sudo("su %s -c 'source %s; %s'" % (user, venvdir, cmd))


def update_site_version(site_version):
    envfile = join(home_directory(SITE_USER), 'site/bin/environment.sh')
    sed(envfile, 'SITE_VERSION=".*"', 'SITE_VERSION="%s"' % site_version, use_sudo=True)


def update_repo(commit=None):
    site_root = join(home_directory(SITE_USER), 'site')
    repodir = join(site_root, SITE_NAME)
    if not files.is_dir(repodir):
        with cd(site_root):
            su('git clone %s %s' % (SITE_REPO, SITE_NAME))
    with cd(repodir):
        su('git fetch')
        if commit is None:
            commit = 'origin/master'
        su('git checkout %s' % commit)


def collectstatic():
    environment = join(home_directory(SITE_USER), 'site/bin/environment.sh')
    djangodir = join(home_directory(SITE_USER), 'site', SITE_NAME, 'companionpages')
    # ignoring logs and media objects in our s3 container
    # this shouldn't be necessary but is a consequence of using django-storages with the boto backend
    # and as of now, django-storages doesn't support separate containers for static and media.
    with cd(djangodir):
        vsu('source %s; ./manage.py collectstatic --noinput --clear --ignore *logs* --ignore *materials* --ignore *articles*' % environment)


def maintenance_enable():
    """Take down the researchcompendia site and enable the maintenance site
    """
    require.nginx.disabled('researchcompendia')
    require.nginx.enabled('maintenance')

def maintenance_disable():
    """Take down the maintenance site and enable the researchcompendia site
    """
    require.nginx.disable('maintenance')
    require.nginx.enable('researchcompendia')


def get_site_version():
    site_line = run('grep SITE_VERSION %s' % join(home_directory(SITE_USER), 'site/bin/environment.sh'))
    match = re.search(r'export SITE_VERSION="(?P<version>[^"]+)', site_line)
    g = match.groupdict()
    return g['version']


def randomstring(n):
    return ''.join(random.choice(string.ascii_letters + string.digits + '~@#%^&*-_') for x in range(n))

def virtualenv_name(commit=None):
    if commit is None:
        repodir = join(home_directory(SITE_USER), 'site', SITE_NAME)
        with cd(repodir):
            commit = run('git rev-parse HEAD').strip()
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    return '%s-%s' % (timestamp, commit)


def template_path(filename):
    return join(FAB_HOME, 'templates', filename)


def mkvirtualenv(virtualenv):
    with cd(join(home_directory(SITE_USER), 'venvs')):
        su('virtualenv %s' % virtualenv)
