# -*- coding: utf-8 -*-
"""_restore command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from cleanroom.location import Location
from cleanroom.generator.command import Command
from cleanroom.generator.systemcontext import SystemContext
from cleanroom.generator.workdir import delete_current_system_directory, restore_work_directory
from cleanroom.printer import debug

import typing


def _restore_base(system_context: SystemContext, base_context: SystemContext) -> None:
    # Clean up:
    assert system_context.ctx
    delete_current_system_directory(system_context.ctx)

    # Set up from base_context:
    restore_work_directory(system_context.ctx,
                           base_context.storage_directory(),
                           system_context.current_system_directory())


def _update_base_context(system_context: SystemContext,
                         base_context: SystemContext) -> None:
    base_unpickle = base_context.unpickle()
    system_context.install_base_context(base_unpickle)


class RestoreCommand(Command):
    """The _restore command."""

    def __init__(self) -> None:
        """Constructor."""
        super().__init__('_restore', syntax='<STATIC> [pretty=<PRETTY>]',
                         help_string='Set the hostname of the system.',
                         file=__file__)

    def validate_arguments(self, location: Location, *args: typing.Any, **kwargs: typing.Any) \
            -> typing.Optional[str]:
        """Validate the arguments."""
        self._validate_arguments_exact(location, 1,
                                       '"{}" needs a base system to restore.',
                                       *args, **kwargs)

        return None

    def __call__(self, location: Location, system_context: SystemContext,
                 *args: typing.Any, **kwargs: typing.Any) -> None:
        """Execute command."""
        base_system = args[0]
        debug('Restoring state from "{}".'.format(base_system))
        base_context = system_context.create_system_context(base_system)

        _restore_base(system_context, base_context)
        _update_base_context(system_context, base_context)

        system_context.run_hooks('_setup')
