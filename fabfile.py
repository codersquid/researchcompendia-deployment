import datetime, string, random
from os.path import join, dirname, abspath
from fabric.api import run, task, env, cd, sudo, local, put
from fabric.contrib.files import sed
from fabtools import require, supervisor, postgres, deb, files
from fabtools.files import upload_template
from fabtools.user import home_directory
import fabtools

env.disable_known_hosts = True
env.user = 'vagrant'
env.hosts = [
    #'researchcompendia.org',
    #'labs.researchcompendia.org',
    # my remote dev box
    #'67.207.156.211',
    'vagrant@127.0.0.1:2222',
]
if env.user == 'vagrant':
    env.key_filename = local('vagrant ssh-config | grep IdentityFile | cut -f4 -d " "', capture=True)
SITE_USER = 'tyler'
SITE_NAME = 'tyler'
SITE_REPO = 'git://github.com/researchcompendia/researchcompendia.git'
SITE_ENVIRONMENT = 'local'
FAB_HOME = dirname(abspath(__file__))


@task
def deploy(version_tag=None):
    supervisor.stop_process(SITE_NAME)
    new_env = virtualenv_name(commit=version_tag)
    mkvirtualenv(new_env)
    update_site_version(new_env)
    update_repo(commit=version_tag)
    install_site_requirements(new_env)
    collectstatic()
    supervisor.start_process(SITE_NAME)


@task
def setup(version_tag=None):
    install_dependencies()
    lockdowns()
    setup_database()
    setup_user()
    update_repo(version_tag)
    setup_django(version_tag)
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


def setup_rabbitmq(user=None):
    if user is None:
        user = SITE_USER
    secret = randomstring(64)
    sudo('rabbitmqctl delete_user guest')
    sudo('rabbitmqctl add_user %s "%s"' % (user, secret))
    sudo('rabbitmqctl set_permissions -p / %s ".*" ".*" ".*"' % user)
    template_dir = join(FAB_HOME, 'templates')
    destination_file = join(home_directory(user), 'site', 'env', 'DJANGO_BROKER_URL')
    upload_template('DJANGO_BROKER_URL', destination_file, use_jinja=True, context={'password': secret},
        template_dir=template_dir, use_sudo=True, chown=True, user=SITE_USER)


def setup_nginx():
    template_dir = join(FAB_HOME, 'templates')
    upload_template('researchcompendia_nginx', '/etc/nginx/sites-available/researchcompendia',
            use_jinja=True, use_sudo=True, template_dir=template_dir)
    # figure out how to do the status conf
    require.nginx.enabled('researchcompendia')


def setup_supervisor():
    template_dir = join(FAB_HOME, 'templates')
    upload_template('researchcompendia_web.conf', '/etc/supervisor/conf.d/researchcompendia_web.conf',
        template_dir=template_dir, use_sudo=True)
    upload_template('celeryd.conf', '/etc/supervisor/conf.d/celeryd.conf', use_sudo=True,
        template_dir=template_dir)
    supervisor.update_config()


def lockdowns():
    # don't share nginx version in header and error pages
    sed('/etc/nginx/nginx.conf', '# server_tokens off;', 'server_tokens off;', use_sudo=True)
    # require keyfile authentication
    sed('/etc/ssh/sshd_config', '^#PasswordAuthentication yes', 'PasswordAuthentication no', use_sudo=True)


def setup_django(version_tag):
    virtualenv = virtualenv_name(commit=version_tag)
    mkvirtualenv(virtualenv)
    update_site_version(virtualenv)
    install_site_requirements(virtualenv)
    collectstatic()
    migrate_and_load_database()


def migrate_and_load_database():
    envdir = join(home_directory(SITE_USER), 'site', 'env')
    djangodir = join(home_directory(SITE_USER), 'site', SITE_NAME, 'companionpages')
    with cd(djangodir):
        vsu('envdir %s ./manage.py syncdb --noinput --migrate' % envdir)
        vsu('envdir %s ./manage.py loaddata fixtures/*' % envdir)


def install_site_requirements(virtualenv):
    home = home_directory(SITE_USER)
    with cd(join(home, 'site', SITE_NAME)):
        vsu('pip install -r requirements/production.txt', virtualenv=virtualenv)


def setup_database():
    require.postgres.server()
    # NOTE: fabtools.require.postgres.user did not allow me to create a user with no pw
    if not postgres.user_exists(SITE_USER):
        su('createuser -S -D -R -w %s' % SITE_USER, 'postgres')
    if not postgres.database_exists(SITE_USER):
        su('createdb -w -O %s %s' % (SITE_USER, SITE_USER), 'postgres')

def setup_user():
    if not fabtools.user.exists(SITE_USER):
        sudo('useradd -s/bin/bash -d/home/%s -m %s' % (SITE_USER, SITE_USER))

    bash_aliases = join(home_directory(SITE_USER), '.bash_aliases')
    put(template_path('_bash_aliases'), bash_aliases, use_sudo=True)
    sudo('chown %s:%s %s' % (SITE_USER, SITE_USER, bash_aliases))

    site_root = join(home_directory(SITE_USER), 'site')
    bindir = join(site_root, 'bin')
    envdir = join(site_root, 'env')
    localenvdir = join(FAB_HOME, 'env', SITE_ENVIRONMENT, '*')

    with cd(home_directory(SITE_USER)):
        su('mkdir -p venvs site')

    with cd(site_root):
        # make directories
        su('mkdir -p logs bin env bin/runnerenv')
        # add site files
        put(template_path('runserver.sh'), bindir, use_sudo=True)
        put(template_path('celeryworker.sh'), bindir, use_sudo=True)
        put(template_path('check_downloads.sh'), bindir, use_sudo=True)
        put(localenvdir, envdir, use_sudo=True)
        sudo('chown -R %s:%s %s' % (SITE_USER, SITE_USER, site_root))


def install_dependencies():
    add_apt_sources()
    require.deb.uptodate_index(max_age={'hour': 1})
    install_debian_packages()
    install_python_packages()


def add_apt_sources():
    deb.add_apt_key(url='http://www.rabbitmq.com/rabbitmq-signing-key-public.asc')
    require.deb.source('rabbitmq-server', 'http://www.rabbitmq.com/debian/', 'testing', 'main')
    require.deb.uptodate_index(max_age={'hour': 1})


def install_debian_packages():
    deb.add_apt_key(url='http://www.rabbitmq.com/rabbitmq-signing-key-public.asc')
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
    runnerenv = join(home_directory(SITE_USER), 'site/bin/runnerenv/SITE_VERSION')
    su('echo %s > %s' % (site_version, runnerenv))


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
    envdir = join(home_directory(SITE_USER), 'site', 'env')
    djangodir = join(home_directory(SITE_USER), 'site', SITE_NAME, 'companionpages')
    # ignoring logs and media objects in our s3 container
    # this shouldn't be necessary but is a consequence of using django-storages with the boto backend
    # and as of now, django-storages doesn't support separate containers for static and media.
    with cd(djangodir):
        vsu('envdir %s ./manage.py collectstatic --ignore *logs* --ignore *materials* --ignore *articles*' % envdir)


def get_site_version():
    return run('cat %s' % join(home_directory(SITE_USER), 'site/bin/runnerenv/SITE_VERSION'))
    

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
    su('source ~/.bash_aliases; mkvirtualenv %s' % virtualenv)
