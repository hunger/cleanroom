# -*- coding: utf-8 -*-
"""pkg_systemd_homed command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from cleanroom.command import Command
from cleanroom.helper.file import chmod, chown, copy, create_file, makedirs
from cleanroom.location import Location
from cleanroom.systemcontext import SystemContext

import textwrap
import typing
import os


class PkgSystemdHomedCommand(Command):
    """The pkg_systemd_homed command."""

    def __init__(self, **services: typing.Any) -> None:
        """Constructor."""
        super().__init__('pkg_systemd_homed', help_string='Setup systemd-homed.',
                         file=__file__, **services)

    def validate(self, location: Location,
                 *args: typing.Any, **kwargs: typing.Any) -> None:
        """Validate the arguments."""
        self._validate_no_arguments(location, *args, **kwargs)

    def __call__(self, location: Location, system_context: SystemContext,
                 *args: typing.Any, **kwargs: typing.Any) -> None:
        """Execute command."""
        
        # enable the daemon (actually set up socket activation)
        self._execute(location.next_line(), system_context,
                      'systemd_enable', 'systemd-homed.service')

        # Install keys into /usr:
        makedirs(system_context, '/usr/share/factory/var/lib/systemd/home',
                 mode=0o700)
        config = os.path.join(self._config_directory(system_context))
        copy(system_context,
             os.path.join(config, 'local.private'),
             '/usr/share/factory/var/lib/systemd/home',
             from_outside=True)
        copy(system_context,
             os.path.join(config, 'local.public'),
             '/usr/share/factory/var/lib/systemd/home',
             from_outside=True)
        chmod(system_context, 0o600, '/usr/share/factory/var/lib/systemd/home/*')
        chown(system_context, 0, 0, '/usr/share/factory/var/lib/systemd/home/*')

        # Set up copying of keys to var:
        create_file(system_context, '/usr/lib/tmpfiles.d/systemd-homed.conf',
                    textwrap.dedent('''\
                    C /var/lib/systemd/home - - - - 
                    ''').encode('utf-8'), mode=0o644)

        # Fix up pam:
        create_file(system_context, '/etc/pam.d/system-auth',
                    textwrap.dedent('''\
                    #%PAM-1.0

                    auth     [success=1 new_authtok_reqd=1 ignore=ignore user_unknown=ignore default=bad] pam_systemd_home.so
                    auth     required   pam_unix.so try_first_pass nullok
                    auth     optional   pam_permit.so
                    auth     required   pam_env.so

                    account  [success=1 new_authtok_reqd=1 ignore=ignore user_unknown=ignore default=bad] pam_systemd_home.so
                    account  required   pam_unix.so
                    account  optional   pam_permit.so
                    account  required   pam_time.so

                    password [success=1 new_authtok_reqd=1 ignore=ignore user_unknown=ignore default=bad] pam_systemd_home.so
                    password required   pam_unix.so try_first_pass nullok sha512 shadow
                    password optional   pam_permit.so

                    session  required   pam_limits.so
                    session  [success=1 new_authtok_reqd=1 ignore=ignore user_unknown=ignore default=bad] pam_systemd_home.so
                    session  required   pam_unix.so
                    session  optional   pam_permit.so
                    ''').encode('utf-8'), mode=0o644, force=True)
