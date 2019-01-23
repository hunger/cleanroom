# -*- coding: utf-8 -*-
"""create command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from cleanroom.location import Location
from cleanroom.generator.command import Command
from cleanroom.generator.helper.generic.file import create_file
from cleanroom.generator.systemcontext import SystemContext

import typing


class CreateCommand(Command):
    """The create command."""

    def __init__(self) -> None:
        """Constructor."""
        super().__init__('create', syntax='<FILENAME> <CONTENTS> [force=True] '
                         '[mode=0o644] [user=UID/name] [group=GID/name]',
                         help_string='Create a file with contents.', file=__file__)

    def validate_arguments(self, location: Location, *args: typing.Any, **kwargs: typing.Any) \
            -> typing.Optional[str]:
        """Validate the arguments."""
        self._validate_args_exact(location, 2,
                                  '"{}" takes a file name and the contents '
                                  'to store in the file.', *args)
        self._validate_kwargs(location, ('force', 'mode', 'user', 'group'),
                              **kwargs)

        return None

    def __call__(self, location: Location, system_context: SystemContext,
                 *args: typing.Any, **kwargs: typing.Any) -> None:
        """Execute command."""
        file_name = args[0]
        to_write = system_context.substitute(args[1]).encode('utf-8')

        create_file(system_context, file_name, to_write, **kwargs)
