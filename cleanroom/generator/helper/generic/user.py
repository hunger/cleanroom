# -*- coding: utf-8 -*-
"""user commands.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from cleanroom.generator.context import Binaries
from cleanroom.generator.systemcontext import SystemContext

import collections
import os.path
import typing


User = collections.namedtuple('User', ['name', 'password', 'uid', 'gid',
                                       'comment', 'home', 'shell'])


def useradd(system_context: SystemContext, user_name: str, *,
            comment: str = '', home: str = '', gid: int = -1, uid: int = -1,
            shell: str = '', groups: str = '', password: str = '',
            expire: typing.Optional[str] = None):
    """Add a new user to the system."""
    command = [system_context.binary(Binaries.USERADD),
               '--root', system_context.fs_directory(), user_name]

    if comment:
        command += ['--comment', comment]

    if home:
        command += ['--home', home]

    if gid >= 0:
        command += ['--gid', str(gid)]

    if uid >= 0:
        command += ['--uid', str(uid)]

    if shell:
        command += ['--shell', shell]

    if groups:
        command += ['--groups', groups]

    if password:
        command += ['--password', password]

    if expire is not None:
        if expire == 'None':
            command.append('--expiredate')
        else:
            command += ['--expiredate', expire]

    system_context.run(*command, outside=True)


def usermod(system_context, user_name, *, comment='', home='', gid=-1, uid=-1,
            lock=None, rename='', shell='', append=False, groups='',
            password='', expire=None) -> None:
    """Modify an existing user."""
    command = [system_context.binary(Binaries.USERMOD),
               '--root', system_context.fs_directory(), user_name]

    if comment:
        command += ['--comment', comment]

    if home:
        command += ['--home', home]

    if gid >= 0:
        command += ['--gid', str(gid)]

    if uid >= 0:
        command += ['--uid', str(uid)]

    if lock is not None:
        if lock:
            command.append('--lock')
        elif not lock:
            command.append('--unlock')

    if expire is not None:
        if expire == 'None':
            command.append('--expiredate')
        else:
            command += ['--expiredate', expire]

    if shell:
        command += ['--shell', shell]

    if rename:
        command += ['--login', rename]

    if append:
        command.append('--append')

    if groups:
        command += ['--groups', groups]

    if password:
        command += ['--password', password]

    if expire is not None:
        command += ['--expiredate', expire]

    system_context.run(*command, outside=True)


def _user_data(passwd_file: str, name: str) -> typing.Optional[User]:
    assert isinstance(name, str)
    if not os.path.isfile(passwd_file):
        return None
    if name == 'root':
        return User('root', 'x', 0, 0, 'root', '/root', '/usr/bin/bash')

    with open(passwd_file, 'r') as passwd:
        for line in passwd:
            if line.endswith('\n'):
                line = line[:-1]
            current_user: typing.List[typing.Any] = line.split(':')
            if current_user[0] == name:
                current_user[2] = int(current_user[2])
                current_user[3] = int(current_user[3])
                return User(*current_user)
    return User('nobody', 'x', 65534, 65534, 'Nobody', '/', '/sbin/nologin')


def user_data(system_context: SystemContext, name: str) -> typing.Optional[User]:
    """Get user data from passwd file."""
    return _user_data(system_context.file_name('/etc/passwd'), name)
