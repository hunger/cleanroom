# -*- coding: utf-8 -*-
"""_setup command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from cleanroom.location import Location
from cleanroom.generator.command import Command
from cleanroom.generator.systemcontext import SystemContext
from cleanroom.generator.workdir import create_work_directory

import os
import typing


def _setup_current_system_directory(system_context):
    create_work_directory(system_context.ctx)

    # Make sure there is /dev/null in the filesystem:
    os.makedirs(system_context.file_name('/dev'))

    system_context.run('/usr/bin/mknod', '--mode=666',
                       system_context.file_name('/dev/null'), 'c', '1', '3',
                       outside=True)
    system_context.run('/usr/bin/mknod', '--mode=666',
                       system_context.file_name('/dev/zero'), 'c', '1', '5',
                       outside=True)
    system_context.run('/usr/bin/mknod', '--mode=666',
                       system_context.file_name('/dev/random'), 'c', '1', '8',
                       outside=True)


class _SetupCommand(Command):
    """The _setup Command."""

    def __init__(self) -> None:
        """Constructor."""
        super().__init__('_setup',
                         help_string='Implicitly run before any '
                         'other command of a system is run.',
                         file=__file__)

    def validate_arguments(self, location: Location, *args: typing.Any, **kwargs: typing.Any) \
            -> typing.Optional[str]:
        self._validate_no_arguments(location, *args, **kwargs)

        return None

    def __call__(self, location: Location, system_context: SystemContext,
                 *args: typing.Any, **kwargs: typing.Any) -> None:
        """Execute command."""
        _setup_current_system_directory(system_context)

        # Make sure systemd does not create /var/lib/* for us!
        os.makedirs(system_context.file_name('/var/lib/machines'))
        os.makedirs(system_context.file_name('/var/lib/portables'))
