# -*- coding: utf-8 -*-
"""The class that holds context data for the executor.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from __future__ import annotations

from .location import Location
from .printer import debug, h2, trace
from .execobject import ExecObject

import os
import os.path
import pickle
import string
import typing


class SystemContext:
    """Context data for the execution os commands."""

    def __init__(self, *,
                 system_name: str,
                 base_system_name: str,
                 scratch_directory: str,
                 systems_definition_directory: str,
                 storage_directory: str,
                 timestamp: str) -> None:
        """Constructor."""
        assert scratch_directory
        assert systems_definition_directory

        self._system_name = system_name
        self._timestamp = timestamp
        self._scratch_directory = scratch_directory
        self._systems_definition_directory = systems_definition_directory
        self._system_storage_directory = os.path.join(storage_directory,
                                                      system_name)
        self._base_storage_directory = ''

        self._base_context: typing.Optional[SystemContext] = None
        self._hooks: typing.Dict[str, typing.List[ExecObject]] = {}
        self._hooks_that_already_ran: typing.List[str] = []
        self._substitutions: typing.MutableMapping[str, str] = {}

        if base_system_name:
            self._base_storage_directory \
                = os.path.join(storage_directory, base_system_name)
            self._install_base_context(base_system_name)

        self._setup_core_substitutions()

    def __enter__(self) -> typing.Any:
        h2('Creating system {}'.format(self._system_name))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False

    @property
    def timestamp(self) -> str:
        return self._timestamp

    @property
    def system_name(self) -> str:
        return self._system_name

    @property
    def system_helper_directory(self) -> str:
        return os.path.join(self._systems_definition_directory, self.system_name)

    @property
    def system_tests_directory(self) -> str:
        return os.path.join(self._systems_definition_directory, 'tests')

    @property
    def scratch_directory(self) -> str:
        return self._scratch_directory

    @property
    def fs_directory(self) -> str:
        return os.path.join(self._scratch_directory, 'fs')

    @property
    def boot_directory(self) -> str:
        return os.path.join(self._scratch_directory, 'boot')

    @property
    def meta_directory(self) -> str:
        return os.path.join(self._scratch_directory, 'meta')

    @property
    def cache_directory(self) -> str:
        return os.path.join(self._scratch_directory, 'cache')

    @property
    def system_storage_directory(self) -> str:
        return self._system_storage_directory

    @property
    def base_storage_directory(self) -> str:
        return self._base_storage_directory

    def __collect_bases(self) -> typing.List[str]:
        bases: typing.List[str] = []
        base_context = self.base_context
        while base_context:
            bases.append(base_context.system_name)
            base_context = base_context.base_context

        return bases

    def _setup_core_substitutions(self) -> None:
        """Core substitutions that may not get overridden by base system."""
        bases: typing.List[str] = self.__collect_bases()

        self.set_substitution('BASE_SYSTEM',
                              bases[0] if bases else '')
        self.set_substitution('BASE_SYSTEM_LIST',
                              ';'.join(bases) if bases else '')

        self.set_substitution('ROOT', self.fs_directory)
        self.set_substitution('META', self.meta_directory)
        self.set_substitution('CACHE', self.cache_directory)
        self.set_substitution('SYSTEM', self.system_name)
        ts = 'unknown' if self.timestamp is None else self.timestamp
        self.set_substitution('TIMESTAMP', ts)

        self.set_substitution('DISTRO_NAME', 'cleanroom')
        self.set_substitution('DISTRO_PRETTY_NAME', 'cleanroom')
        self.set_substitution('DISTRO_ID', 'clrm')
        self.set_substitution('DISTRO_VERSION', ts)
        self.set_substitution('DISTRO_VERSION_ID', ts)

        self.set_substitution('DEFAULT_VG', '')

        self.set_substitution('IMAGE_FS', 'btrfs')
        self.set_substitution('IMAGE_OPTIONS', 'rw,subvol=/.images')
        self.set_substitution('IMAGE_DEVICE', '/dev/disk/by-partlabel/fs_btrfs')

    # Handle Hooks:
    def _add_hook(self, hook: str, exec_obj: ExecObject) -> None:
        """Add a hook."""
        self._hooks.setdefault(hook, []).append(exec_obj)
        trace('Added hook "{}": It now has {} entries.'.format(hook, len(self._hooks[hook])))

    def add_hook(self, location: Location, hook: str,
                 *args: typing.Any, **kwargs: typing.Any) -> None:
        """Add a hook."""
        assert len(args) > 0
        self._add_hook(hook, ExecObject(location=location,
                                        command=args[0],
                                        args=args[1:],
                                        kwargs=kwargs))

    def hooks(self, hook_name: str) -> typing.Sequence[ExecObject]:
        """Run all the registered hooks."""
        return self._hooks.get(hook_name, [])

    # Handle substitutions:
    @property
    def substitutions(self) -> typing.Mapping[str, str]:
        return self._substitutions

    def set_substitution(self, key: str, value: str) -> None:
        """Add a substitution to the substitution table."""
        self._substitutions[key] = value
        debug('Added substitution: "{}"="{}".'.format(key, value))

    def substitution(self, key: str,
                     default_value: typing.Optional[str] = None) -> typing.Any:
        """Get substitution value."""
        return self.substitutions.get(key, default_value)

    def has_substitution(self, key: str) -> bool:
        """Check wether a substitution is defined."""
        return key in self.substitutions

    def substitute(self, text: str) -> str:
        """Substitute variables in text."""
        return string.Template(text).substitute(**self.substitutions)

    def file_name(self, path: str) -> str:
        return os.path.join(self.fs_directory, path)

    @property
    def base_context(self) -> typing.Optional[SystemContext]:
        return self._base_context

    # Store/Restore a system:
    def _install_base_context(self, base_system_name: str) -> None:
        """Set up base context."""
        base_context = self._unpickle(os.path.join(self.base_storage_directory,
                                                   'meta', 'pickle_jar.bin'))

        self._base_context = base_context
        self._timestamp = base_context._timestamp
        self._hooks = base_context._hooks
        self._substitutions = base_context._substitutions

    def _unpickle(self, pickle_jar: str) -> SystemContext:
        """Create a new system_context by unpickling a file."""
        with open(pickle_jar, 'rb') as pj:
            base_context = pickle.load(pj)
        trace('Base context was unpickled.')

        return base_context


    def pickle(self) -> None:
        """Pickle this system_context."""
        pickle_jar = os.path.join(self.meta_directory, 'pickle_jar.bin')

        # Remember stuff that should not get saved:
        hooks_that_ran = self._hooks_that_already_ran
        self._hooks_that_already_ran = []

        trace('Pickling system_context into {}.'.format(pickle_jar))
        with open(pickle_jar, 'wb') as pj:
            pickle.dump(self, pj)

        # Restore state that should not get saved:
        self._hooks_that_already_ran = hooks_that_ran