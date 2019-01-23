# -*- coding: utf-8 -*-
"""Create and manage the work directory.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from ..exceptions import GenerateError, PrepareError
from ..helper.btrfs import create_snapshot, create_subvolume, \
    delete_subvolume_recursive, has_subvolume
from ..helper.mount import umount_all
from ..printer import trace
from .context import Binaries, Context

import os
import os.path
import tempfile
import typing


class WorkDir:
    """Parse a container.conf file."""

    def __init__(self, ctx: Context, *, work_directory: str = None,
                 clear_work_directory: bool = False,
                 clear_storage: bool = False) -> None:
        """Constructor."""
        self._path = work_directory
        self._temp_directory: typing.Optional[tempfile.TemporaryDirectory] \
            = None

        if work_directory:
            if not os.path.exists(work_directory):
                trace('Creating permanent work directory in "{}".'
                      .format(work_directory))
                os.makedirs(work_directory, 0o700)
            else:
                trace('Using existing work directory in "{}".'
                      .format(work_directory))
                if not umount_all(work_directory):
                    raise PrepareError('Failed to unmount mount in work '
                                       'directory "{}".'
                                       .format(work_directory))
                if clear_work_directory:
                    delete_current_system_directory(ctx, work_directory=work_directory)
                if clear_storage:
                    _clear_storage(ctx, work_directory)
        else:
            trace('Creating temporary work directory.')
            self._temp_directory = tempfile.TemporaryDirectory(prefix='clrm-',
                                                               dir='/var/tmp')
            self._path = self._temp_directory.name

    def __del__(self) -> None:
        """Destructor."""
        self.cleanup()

    def __enter__(self) -> typing.Any:
        """Enter a Context."""
        if self._temp_directory:
            return self._temp_directory.__enter__()
        else:
            return self._path

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit a context."""
        if self._temp_directory:
            tmp_directory = self._temp_directory
            self._temp_directory = None
            return tmp_directory.__exit__(exc_type, exc_val, exc_tb)
        return False

    def path(self) -> typing.Optional[str]:
        """Name of the work directory."""
        return self._path

    def cleanup(self) -> None:
        """Clean up the work directory (if necessary)."""
        if self._temp_directory:
            self._temp_directory.cleanup()
            self._temp_directory = None


def _subdirectories(directory: str) -> typing.List[str]:
    return [os.path.join(directory, name) for name in os.listdir(directory)
            if os.path.isdir(os.path.join(directory, name))]


def _create_subvolume(ctx: Context, directory: str,
                      exists_ok: bool = False) -> None:
    if has_subvolume(directory, command=ctx.binary(Binaries.BTRFS)):
        if exists_ok:
            trace('Subvolume {} already exists, continuing.'.format(directory))
            return
        else:
            raise GenerateError('Directory {} already exists when trying to create a subvolume.'.format(directory))
    elif os.path.isdir(directory):
            raise GenerateError('Directory {} already exists and is not a subvolume.'.format(directory))

    create_subvolume(directory, command=ctx.binary(Binaries.BTRFS))


def delete_work_directory(ctx: Context, *,
                          work_directory: typing.Optional[str] = None) \
        -> None:
    wd = work_directory or ctx.work_directory()
    assert wd
    trace('Deleting work directory {}.'.format(wd))
    delete_subvolume_recursive(wd, command=ctx.binary(Binaries.BTRFS))


def delete_current_system_directory(ctx: Context, *,
                                    work_directory: typing.Optional[str] = None) \
        -> None:
    wd = work_directory or ctx.work_directory()
    assert wd
    sd = Context.current_system_directory_from_work_directory(wd)

    trace('Deleting current system directory {}.'.format(wd))
    if os.path.exists(sd):
        delete_subvolume_recursive(sd, command=ctx.binary(Binaries.BTRFS))


def create_work_directory(ctx: Context) -> None:
    wd = ctx.work_directory()
    assert wd
    sd = Context.current_system_directory_from_work_directory(wd)

    trace('Create work directory {}.'.format(wd))
    if not os.path.exists(wd):
        os.makedirs(wd)
    _create_subvolume(ctx, sd, exists_ok=True)
    _create_subvolume(ctx, os.path.join(sd, 'cache'))
    _create_subvolume(ctx, os.path.join(sd, 'fs'))
    _create_subvolume(ctx, os.path.join(sd, 'boot'))
    _create_subvolume(ctx, os.path.join(sd, 'meta'))


def store_work_directory(ctx: Context,
                         system_directory: str,
                         storage_directory: str) -> None:
    trace('Store work directory {} in {}.'
          .format(system_directory, storage_directory))

    create_subvolume(storage_directory, command=ctx.binary(Binaries.BTRFS))
    create_snapshot(os.path.join(system_directory, 'fs'),
                    os.path.join(storage_directory, 'fs'),
                    command=ctx.binary(Binaries.BTRFS), read_only=True)
    create_snapshot(os.path.join(system_directory, 'boot'),
                    os.path.join(storage_directory, 'boot'),
                    command=ctx.binary(Binaries.BTRFS), read_only=True)
    create_snapshot(os.path.join(system_directory, 'meta'),
                    os.path.join(storage_directory, 'meta'),
                    command=ctx.binary(Binaries.BTRFS), read_only=True)


def restore_work_directory(ctx: Context,
                           storage_directory: str,
                           system_directory: str) -> None:
    trace('Restore storage directory {} to {}.'
          .format(storage_directory, system_directory))

    _create_subvolume(ctx, system_directory, exists_ok=True)
    _create_subvolume(ctx, os.path.join(system_directory, 'cache'))
    create_snapshot(os.path.join(storage_directory, 'fs'),
                    os.path.join(system_directory, 'fs'),
                    command=ctx.binary(Binaries.BTRFS))
    create_snapshot(os.path.join(storage_directory, 'boot'),
                    os.path.join(system_directory, 'boot'),
                    command=ctx.binary(Binaries.BTRFS))
    create_snapshot(os.path.join(storage_directory, 'meta'),
                    os.path.join(system_directory, 'meta'),
                    command=ctx.binary(Binaries.BTRFS))


def _clear_storage(ctx: Context, work_directory: str) -> None:
    storage_directory = Context.storage_directory_from_work_directory(work_directory)
    assert storage_directory
    if os.path.isdir(storage_directory):
        delete_subvolume_recursive(storage_directory, command=ctx.binary(Binaries.BTRFS))
        os.rmdir(storage_directory)
