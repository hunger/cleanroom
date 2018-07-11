# -*- coding: utf-8 -*-
"""Manage pacman and pacstrap calls.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from cleanroom.generator.context import Binaries
from cleanroom.exceptions import GenerateError
from cleanroom.printer import info

import os
import os.path


def _package_type(system_context):
    return system_context.substitution('CLRM_PACKAGE_TYPE', None)


def _set_package_type(system_context):
    system_context.set_substitution('CLRM_PACKAGE_TYPE', 'pacman')


def target_gpg_directory():
    """Return the gpg directory path inside the system filesystem."""
    return '/usr/lib/pacman/gpg'


def host_gpg_directory(system_context):
    """Return the host location of the pacman GPG configuration."""
    return system_context.file_name(target_gpg_directory())


def target_db_directory():
    """Return the pacman db directory path inside the system filesystem."""
    return '/usr/lib/pacman/db'


def host_db_directory(system_context):
    """Return the host location of the pacman DB."""
    return system_context.file_name(target_db_directory())


def target_cache_directory():
    """Return the target pacman cache directory path."""
    return '/var/cache/pacman'


def host_cache_directory(system_context):
    """Return the host location of the pacman cache."""
    return system_context.file_name(target_cache_directory())


def initial_pacstrap_configuration_file(system_context):
    """Return the host configuration for initial pacstrap run."""
    init_config_path = os.path.join(
        system_context.system_definition_directory(),
        'pacstrap.conf')
    if not os.path.isfile(init_config_path):
        raise GenerateError('Could not find: "{}".'.format(init_config_path))
    return init_config_path


def pacstrap(system_context, config, *packages):
    """Run pacstrap on host."""
    assert(_package_type(system_context) is None)

    _sync_host(system_context, config)

    system_context.run(
        system_context.binary(Binaries.PACSTRAP),
        '-c',  # use cache on host
        '-d',  # No mount point
        '-M',  # Do not copy host mirrorlist
        '-G',  # Do not copy host keyring
        '-C', config,  # Use config file
        system_context.fs_directory(),
        '--dbpath={}'.format(host_db_directory(system_context)),
        '--gpgdir={}'.format(host_gpg_directory(system_context)),
        *packages,
        work_directory=system_context.ctx.systems_directory(),
        outside=True)

    _set_package_type(system_context)


def _sync_host(system_context, config):
    """Run pacman -Syu on the host."""
    os.makedirs(host_db_directory(system_context))
    system_context.run(
        system_context.binary(Binaries.PACMAN),
        '-Syu', '--config', config,
        '--dbpath', host_db_directory(system_context),
        outside=True)


def pacman(system_context, *packages, remove=False):
    """Use pacman to install packages."""
    assert(_package_type(system_context) == 'pacman')

    info('Installing {}'.format(', '.join(packages)))

    if remove:
        system_context.run(
            system_context.binary(Binaries.PACMAN),
            '-Rs', '--noconfirm', *packages)
    else:
        system_context.run(
            system_context.binary(Binaries.PACMAN),
            '-S', '--noconfirm', '--needed', *packages)