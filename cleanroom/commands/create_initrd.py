# -*- coding: utf-8 -*-
"""create_initrd command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""

from cleanroom.binarymanager import Binaries
from cleanroom.command import Command
from cleanroom.helper.file import copy, create_file, remove, move
from cleanroom.helper.run import run
from cleanroom.location import Location
from cleanroom.systemcontext import SystemContext
from cleanroom.printer import info

import os
import textwrap
import typing


def _cleanup_extra_files(
    location: Location, system_context: SystemContext, *files: str
) -> None:
    location.set_description("Remove extra mkinitcpio files")


class CreateInitrdCommand(Command):
    """The create_initrd command."""

    def __init__(self, **services: typing.Any) -> None:
        """Constructor."""
        super().__init__(
            "create_initrd",
            syntax="<INITRD_FILE>",
            help_string="Create an initrd.",
            file=__file__,
            **services
        )

    def validate(
        self, location: Location, *args: typing.Any, **kwargs: typing.Any
    ) -> None:
        """Validate the arguments."""
        self._validate_arguments_exact(
            location, 1, '"{}" takes an initrd to create.', *args, **kwargs
        )

    def _fix_mkinitcpio_conf(
        self, location: Location, system_context: SystemContext, name: str
    ):
        extra = system_context.substitution_expanded(
            "MKINITCPIO_EXTRA_{}".format(name), ""
        )
        if extra:
            extra += " "
        extra += system_context.substitution_expanded(
            "INITRD_EXTRA_{}".format(name), ""
        )
        if extra:
            self._execute(
                location.next_line(),
                system_context,
                "sed",
                "/^{}=/ c{}=({})".format(name, name, extra,),
                "/etc/mkinitcpio.conf",
            )

    def _install_mkinitcpio(
        self, location: Location, system_context: SystemContext,
    ) -> typing.Sequence[str]:
        to_clean_up = ["/etc/mkinitcpio.d", "/etc/mkinitcpio.conf", "/boot/vmlinu*"]

        location.set_description("Install mkinitcpio")
        self._execute(location, system_context, "pacman", "mkinitcpio")

        location.set_description("Fix up mkinitcpio.conf")
        self._execute(
            location.next_line(),
            system_context,
            "sed",
            "/^HOOKS=/ "
            "cHOOKS=(base systemd keyboard sd-vconsole "
            "sd-encrypt block sd-lvm2 filesystems btrfs sd-shutdown)",
            "/etc/mkinitcpio.conf",
        )

        self._fix_mkinitcpio_conf(location.next_line(), system_context, "HOOKS")
        self._fix_mkinitcpio_conf(location.next_line(), system_context, "FILES")
        self._fix_mkinitcpio_conf(location.next_line(), system_context, "BINARIES")
        self._fix_mkinitcpio_conf(location.next_line(), system_context, "MODULES")

        location.set_description("Create mkinitcpio presets")
        create_file(
            system_context,
            "/etc/mkinitcpio.d/cleanroom.preset",
            textwrap.dedent(
                """\
                    # mkinitcpio preset file for cleanroom

                    ALL_config="/etc/mkinitcpio.conf"
                    ALL_kver="/boot/vmlinuz"

                    PRESETS=('default')

                    default_image="/boot/initramfs.img"
                    """
            ).encode("utf-8"),
        )

        return to_clean_up

    def _remove_mkinitcpio(
        self, location: Location, system_context: SystemContext
    ) -> None:
        # FIXME: Remove mkinitcpio once linux and ostree no longer depend on it!
        self._execute(
            location,
            system_context,
            "pacman",
            "mkinitcpio",
            "--assume-installed",
            "initramfs",
            "--assume-installed",
            "mkinitcpio",
            remove=True,
        )
        remove(system_context, "/boot/vmlinuz")

    def register_substitutions(self) -> typing.List[typing.Tuple[str, str, str]]:
        return [
            ("MKINITCPIO_EXTRA_MODULES", "", "Extra modules to add to the initrd",),
            ("MKINITCPIO_EXTRA_HOOKS", "", "Extra hooks to add to the initrd",),
            ("MKINITCPIO_EXTRA_BINARIES", "", "Extra binaries to add to the initrd",),
            ("MKINITCPIO_EXTRA_FILES", "", "Extra files to add to the initrd",),
        ]

    def __call__(
        self,
        location: Location,
        system_context: SystemContext,
        *args: typing.Any,
        **kwargs: typing.Any
    ) -> None:
        """Execute command."""
        if not os.path.exists(os.path.join(system_context.boot_directory, "vmlinuz")):
            info("Skipping initrd generation: No vmlinuz in boot directory.")
            return

        initrd = args[0]

        to_clean_up: typing.List[str] = []
        to_clean_up += "/boot/vmlinuz"
        to_clean_up += self._install_mkinitcpio(location, system_context)

        copy(
            system_context,
            os.path.join(system_context.boot_directory, "vmlinuz"),
            "/boot/vmlinuz",
            from_outside=True,
        )

        run(
            "/usr/bin/mkinitcpio",
            "-p",
            "cleanroom",
            chroot=system_context.fs_directory,
            chroot_helper=self._binary(Binaries.CHROOT_HELPER),
        )

        os.makedirs(os.path.dirname(initrd), exist_ok=True)
        move(system_context, "/boot/initramfs.img", initrd, to_outside=True)

        # _cleanup_extra_files(location, system_context, *to_clean_up)
        # self._remove_mkinitcpio(location, system_context)

        assert os.path.isfile(initrd)
