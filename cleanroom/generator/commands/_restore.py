# -*- coding: utf-8 -*-
"""_restore command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from cleanroom.generator.command import Command
from cleanroom.generator.context import Binaries
from cleanroom.generator.systemcontext import SystemContext
from cleanroom.generator.workdir import delete_current_system_directory, restore_work_directory

from cleanroom.printer import debug

import os


class RestoreCommand(Command):
    """The _restore command."""

    def __init__(self):
        """Constructor."""
        super().__init__('_restore', syntax='<STATIC> [pretty=<PRETTY>]',
                         help='Set the hostname of the system.',
                         file=__file__)

    def validate_arguments(self, location, *args, **kwargs):
        """Validate the arguments."""
        self._validate_arguments_exact(location, 1,
                                       '"{}" needs a base system to restore.',
                                       *args, **kwargs)

    def __call__(self, location, system_context, *args, **kwargs):
        """Execute command."""
        base_system = args[0]
        debug('Restoring state from "{}".'.format(base_system))
        base_context = system_context.create_system_context(base_system)

        self._restore_base(system_context, base_context)
        self._update_base_context(system_context, base_context)

        system_context.run_hooks('_setup')

    def _restore_base(self, system_context, base_context):
        # Clean up:
        delete_current_system_directory(system_context.ctx)

        # Set up from base_context:
        restore_work_directory(system_context.ctx,
                               base_context.storage_directory(),
                               system_context.current_system_directory())

    def _update_base_context(self, system_context, base_context):
        base_unpickle = base_context.unpickle()
        system_context.install_base_context(base_unpickle)
