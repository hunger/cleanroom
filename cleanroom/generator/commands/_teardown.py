# -*- coding: utf-8 -*-
"""_teardown command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from cleanroom.generator.command import Command
from cleanroom.generator.context import Binaries
from cleanroom.generator.systemcontext import SystemContext
from cleanroom.helper.btrfs import delete_subvolume_recursive
from cleanroom.location import Location
from cleanroom.printer import debug

import typing


def _store(location: Location, system_context: SystemContext) -> None:
    system_context.execute(location.next_line(), '_store')


def _clean_temporary_data(system_context: SystemContext) -> None:
    """Clean up temporary data."""
    assert system_context.ctx
    current_system_directory = system_context.current_system_directory()
    assert current_system_directory
    debug('Removing {}.'.format(current_system_directory))

    delete_subvolume_recursive(current_system_directory,
                               command=system_context.ctx.binary(Binaries.BTRFS))


class _TeardownCommand(Command):
    """The _teardown Command."""

    def __init__(self) -> None:
        """Constructor."""
        super().__init__('_teardown',
                         help_string='Implicitly run after any other command of a '
                         'system is run.', file=__file__)

    def validate_arguments(self, location: Location, *args: typing.Any, **kwargs: typing.Any) \
            -> typing.Optional[str]:
        self._validate_no_arguments(location, *args, **kwargs)

        return None

    def __call__(self, location: Location, system_context: SystemContext,
                 *args: typing.Any, **kwargs: typing.Any) -> None:
        """Execute command."""
        system_context.run_hooks('_teardown')
        system_context.run_hooks('testing')

        system_context.pickle()

        _store(location, system_context)
        _clean_temporary_data(system_context)
