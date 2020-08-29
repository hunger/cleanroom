# -*- coding: utf-8 -*-
"""create_clrm_initrd_extra command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""

from cleanroom.exceptions import GenerateError
from cleanroom.binarymanager import Binaries
from cleanroom.command import Command
from cleanroom.helper.run import run
from cleanroom.location import Location
from cleanroom.systemcontext import SystemContext
from cleanroom.printer import debug, info, trace

import os
from shutil import copyfile
from tempfile import TemporaryDirectory
import typing


_modules: typing.Set[str] = set()
_extra_modules: typing.List[str] = []


def _populate_modules(fs_directory: str):
    module_directory = os.path.join(fs_directory, "usr/lib/modules")

    for _, _, files in os.walk(module_directory):
        for f in files:
            module_name = os.path.basename(f)

            ko_pos = module_name.find(".ko")
            if ko_pos >= 0:
                module_name = module_name[:ko_pos]

            trace(f"Found a kernel module: {module_name}.")
            _modules.add(module_name)


def _device_ify(device: str) -> str:
    if not device:
        return ""
    if device.startswith("PARTLABEL="):
        device = "/dev/disk/by-partlabel/" + device[10:]
    elif device.startswith("LABEL="):
        device = "/dev/disk/by-label/" + device[6:]
    elif device.startswith("PARTUUID="):
        device = "/dev/disk/by-partuuid/" + device[9:]
    elif device.startswith("UUID="):
        device = "/dev/disk/by-uuid/" + device[5:]
    elif device.startswith("ID="):
        device = "/dev/disk/by-id/" + device[3:]
    elif device.startswith("PATH="):
        device = "/dev/disk/by-path/" + device[5:]
    assert device.startswith("/dev/")
    return device


def _escape_device(device: str) -> str:
    device = _device_ify(device)

    device = device.replace("-", "\\x2d")
    device = device.replace("=", "\\x3d")
    device = device.replace(";", "\\x3b")
    device = device.replace("/", "-")

    return device[1:]


def _trim_empty_directories(root_dir: str):
    for root, directories, files in os.walk(root_dir, topdown=False):
        if not directories and not files:
            os.removedirs(os.path.join(root_dir, root))


def _tokenize_line(line: str) -> typing.List[str]:
    token = ""
    token_list: typing.List[str] = []
    while line:
        current_char = line[0]
        line = line[1:]

        if current_char == "#":
            line = ""
            continue

        if current_char.isspace():
            if token:
                token_list.append(token)
                token = ""
            continue

        token += current_char

    if token:
        token_list.append(token)

    return token_list


def _replace(
    contents: str, replacements: typing.Dict[str, typing.Optional[str]]
) -> typing.Tuple[str, bool]:
    replacement_failed = False

    did_replacement = False

    input_contents = contents

    for k, v in replacements.items():
        r = "{" + k + "}"
        if r in contents:
            did_replacement = True
            old_contents = contents
            if v is None:
                debug(f'    SKIPPING replacement of "{r}": value is None.')
                replacement_failed = True
            else:
                debug(f'    Replacing "{r}" with "{v}".')
                contents = contents.replace(r, v)
                assert old_contents != contents

    assert not did_replacement or replacement_failed or input_contents != contents

    return (contents, replacement_failed)


def _do_file(
    is_optional: bool,
    *args: str,
    base_dir: str,
    fs_dir: str,
    system_fs_directory: str,
    replacements: typing.Dict[str, typing.Optional[str]],
):
    # validate the inputs:
    assert len(args) >= 1 and len(args) <= 2
    src = args[0]
    dest = ""
    if len(args) == 2:
        dest = args[1]
    else:
        assert os.path.isabs(src)
        dest = src
    assert src and dest
    assert os.path.isabs(dest)

    (real_src, src_failed) = _replace(src, replacements)
    (real_dest, dest_failed) = _replace(dest, replacements)

    if src_failed and not is_optional:
        raise GenerateError(f"FILE failed: {src} failed to replace")
    if dest_failed and not is_optional:
        raise GenerateError(f"FILE failed: {dest} failed to replace.")

    replace_contents = False
    if os.path.isabs(real_src):
        trace(f"{real_src} is absolute, resolving relative to {system_fs_directory}.")
        real_src = os.path.join(system_fs_directory, real_src[1:])
    else:
        replace_contents = True
        trace(f"{real_src} is not absolute, resolving relative to {base_dir}.")
        real_src = os.path.join(base_dir, real_src)

    if not os.path.isfile(real_src):
        trace(f"FILE: Source file {real_src} does not exist.")
        if is_optional:
            return
        else:
            raise GenerateError(f"FILE: Source file {src} does not exist.")

    real_dest = os.path.join(fs_dir, real_dest[1:])

    if not os.path.exists(os.path.dirname(real_dest)):
        os.makedirs(os.path.dirname(real_dest))

    trace(f"FILE: Copying data from {real_src} -> {real_dest}.")

    if replace_contents:
        with open(real_src, "r") as fd:
            contents = fd.read()

        (contents, fail) = _replace(contents, replacements)
        if fail:
            if is_optional:
                return
            else:
                raise GenerateError("FILE failed: contents failed to replace.")

        with open(real_dest, "w") as fd:
            fd.write(contents)
    else:
        copyfile(real_src, real_dest)

    assert os.path.isfile(real_dest)

    debug(
        f"FILE action {real_src} -> {real_dest} (optional={is_optional}, replace_contents={replace_contents}): SUCCESS"
    )


def _do_binary(
    is_optional: bool,
    *args: str,
    base_dir: str,
    fs_dir: str,
    system_fs_directory: str,
    replacements: typing.Dict[str, typing.Optional[str]],
):
    assert len(args) >= 1 and len(args) <= 2
    src = args[0]
    dest = ""
    if len(args) == 2:
        dest = args[1]
    else:
        assert os.path.isabs(src)
        dest = src
    assert src and dest
    assert os.path.isabs(dest)

    (real_src, src_failed) = _replace(
        os.path.join(system_fs_directory, src[1:]), replacements
    )
    (real_dest, dest_failed) = _replace(os.path.join(fs_dir, dest[1:]), replacements)

    if src_failed and not is_optional:
        raise GenerateError(f"BINARY failed: {src} failed to replace")
    if dest_failed and not is_optional:
        raise GenerateError(f"BINARY failed: {dest} failed to replace.")

    if os.path.isfile(real_src):
        trace(f"BINARY: Copying data from {real_src} -> {real_dest}.")

        if not os.path.exists(os.path.dirname(real_dest)):
            os.makedirs(os.path.dirname(real_dest))

        copyfile(real_src, real_dest)
        assert os.path.isfile(real_dest)
        # Fix up permissions and ownership:
        os.chmod(real_dest, 0o755)
        os.chown(real_dest, 0, 0)
    else:
        if not is_optional:
            raise GenerateError(f"BINARY does not exist at {real_src}.")
        trace(f"Binary {src} not installed into extra initrd!")

    ### TODO: Handle dependencies!

    debug(f"BINARY action {src} -> {dest} (optional={is_optional}): SUCCESS")


def _do_link(
    is_optional: bool,
    *args: str,
    base_dir: str,
    fs_dir: str,
    system_fs_directory: str,
    replacements: typing.Dict[str, typing.Optional[str]],
):
    assert len(args) == 2
    src = args[0]
    assert os.path.isabs(src)
    dest = args[1]

    (real_src, src_failed) = _replace(os.path.join(fs_dir, src[1:]), replacements)
    (real_dest, dest_failed) = _replace(dest, replacements)

    if src_failed:
        if is_optional:
            return
        else:
            raise GenerateError(f"LINK failed: {src} failed to replace")
    if dest_failed:
        if is_optional:
            return
        else:
            raise GenerateError(f"LINK failed: {dest} failed to replace.")

    if not os.path.isdir(os.path.dirname(real_src)):
        os.makedirs(os.path.dirname(real_src))

    if not real_dest.startswith("/dev/"):
        if os.path.isabs(dest):
            initrd_dest = os.path.join(fs_dir, real_dest[1:])
        else:
            initrd_dest = os.path.join(os.path.dirname(real_src), real_dest)

        if not os.path.exists(initrd_dest):
            trace(
                f"Link target {dest} does not exist in extra initrd!\n    full target path: {initrd_dest}...\n    is_optional: {is_optional}...\n    files: {os.listdir(os.path.dirname(initrd_dest))}..."
            )
            if is_optional:
                return
            else:
                raise GenerateError(f"LINK target {dest} does not exist.")

    trace(f"LINK: Creating symlink from {real_src} -> {real_dest}.")
    os.symlink(real_dest, real_src)

    assert os.path.islink(real_src)

    debug(f"LINK action {src} -> {dest} (optional={is_optional}): SUCCESS")


def _do_module(
    is_optional: bool,
    *args: str,
    base_dir: str,
    fs_dir: str,
    system_fs_directory: str,
    replacements: typing.Dict[str, typing.Optional[str]],
):
    assert len(args) == 1
    module = args[0]

    if not module in _modules:
        if not is_optional:
            raise GenerateError(f"MODULE {module} was not found.")
        trace(f"Module {module} not installed into extra initrd!")
        return

    debug(f"MODULE action {module} (optional={is_optional}): SUCCESS")
    _extra_modules.append(module)

    module_file = os.path.basename(base_dir)
    module_file_path = os.path.join(fs_dir, f"etc/modules-load.d/{module_file}.conf")
    contents = ""

    if not os.path.exists(os.path.dirname(module_file_path)):
        os.makedirs(os.path.dirname(module_file_path))

    if os.path.exists(module_file_path):
        with open(module_file_path, "r") as fd_in:
            contents = fd_in.read()

    if not contents:
        contents += f"# Load modules for {module_file}:\n"
    contents += module

    with open(module_file_path, "w") as fd_out:
        fd_out.write(contents)


def _do(
    action: str,
    is_optional: bool,
    *args: str,
    base_dir: str,
    fs_dir: str,
    system_fs_directory: str,
    replacements: typing.Dict[str, typing.Optional[str]],
):
    trace(
        f"Do {action} {args} (is_optional={is_optional})\n    base_dir: {base_dir}...\n    fs_dir: {fs_dir}...\n    system_fs_directory: {system_fs_directory}..."
    )
    if action == "FILE":
        _do_file(
            is_optional,
            *args,
            base_dir=base_dir,
            fs_dir=fs_dir,
            system_fs_directory=system_fs_directory,
            replacements=replacements,
        )
    elif action == "BINARY":
        _do_binary(
            is_optional,
            *args,
            base_dir=base_dir,
            fs_dir=fs_dir,
            system_fs_directory=system_fs_directory,
            replacements=replacements,
        )
    elif action == "LINK":
        _do_link(
            is_optional,
            *args,
            base_dir=base_dir,
            fs_dir=fs_dir,
            system_fs_directory=system_fs_directory,
            replacements=replacements,
        )
    elif action == "MODULE":
        _do_module(
            is_optional,
            *args,
            base_dir=base_dir,
            fs_dir=fs_dir,
            system_fs_directory=system_fs_directory,
            replacements=replacements,
        )
    else:
        raise GenerateError("Unknown keyword {action} in initrd contents file.")


def _parse_line(
    line: str,
    *,
    base_dir: str,
    fs_dir: str,
    system_fs_directory: str,
    replacements: typing.Dict[str, typing.Optional[str]],
):
    trace(f'Parsing line "{line}".')
    tokens = _tokenize_line(line)

    is_optional = False
    action = ""

    while tokens:
        current = tokens[0]
        tokens = tokens[1:]

        if current == "OPTIONAL":
            is_optional = True
            if action:
                _do(
                    action,
                    is_optional,
                    *tokens,
                    base_dir=base_dir,
                    fs_dir=fs_dir,
                    system_fs_directory=system_fs_directory,
                    replacements=replacements,
                )
                break
            continue

        if action:
            _do(
                action,
                is_optional,
                current,
                *tokens,
                base_dir=base_dir,
                fs_dir=fs_dir,
                system_fs_directory=system_fs_directory,
                replacements=replacements,
            )
            break
        else:
            action = current


class CreateClrmInitrdExtraCommand(Command):
    """The create_clrm_initrd_extra command."""

    def __init__(self, **services: typing.Any) -> None:
        """Constructor."""
        super().__init__(
            "create_clrm_initrd_extra",
            syntax="<INITRD_FILE>",
            help_string="Create CLRM-specific initrd extra parts.",
            file=__file__,
            **services,
        )

        self._vg = ""
        self._image_fs = ""
        self._image_device = ""
        self._image_options = ""
        self._full_name = ""

    def validate(
        self, location: Location, *args: typing.Any, **kwargs: typing.Any
    ) -> None:
        """Validate the arguments."""
        self._validate_arguments_exact(
            location, 1, '"{}" takes an initrd to create.', *args, **kwargs
        )

    def register_substitutions(self) -> typing.List[typing.Tuple[str, str, str]]:
        return [
            ("IMAGE_FS", "ext2", "The filesystem type to load clrm-images from",),
            ("IMAGE_DEVICE", "", "The device to load clrm-images from",),
            (
                "IMAGE_OPTIONS",
                "rw",
                "The filesystem options to mount the IMAGE_DEVICE with",
            ),
            (
                "DEFAULT_VG",
                "",
                "The volume group to look for clrm rootfs/verity partitions on",
            ),
        ]

    def _process_contents_file(
        self,
        contents_file: str,
        *,
        fs_dir: str,
        system_fs_directory: str,
        replacements: typing.Dict[str, typing.Optional[str]],
    ):
        debug(f"Processing initrd setup file {contents_file}.")
        base_dir = os.path.dirname(contents_file)
        with open(contents_file, "r") as contents:
            for line in contents:
                _parse_line(
                    line,
                    base_dir=base_dir,
                    fs_dir=fs_dir,
                    system_fs_directory=system_fs_directory,
                    replacements=replacements,
                )
        debug(f"Done with initrd setup file {contents_file}.")

    def _process_helper_folders(
        self,
        *,
        helper_dir: str,
        fs_dir: str,
        system_fs_directory: str,
        replacements: typing.Dict[str, typing.Optional[str]],
    ):
        for dir in os.listdir(helper_dir):
            contents_file = os.path.join(helper_dir, dir, "contents")
            if os.path.isfile(contents_file):
                self._process_contents_file(
                    contents_file,
                    fs_dir=fs_dir,
                    system_fs_directory=system_fs_directory,
                    replacements=replacements,
                )
        trace(f"All helper folders processed!")

    def _create_initrd(
        self,
        initrd: str,
        *,
        helper_dir: str,
        system_fs_directory: str,
        replacements: typing.Dict[str, typing.Optional[str]],
    ):
        with TemporaryDirectory(prefix="clrm_initrd_") as fs_dir:
            self._process_helper_folders(
                helper_dir=helper_dir,
                fs_dir=fs_dir,
                system_fs_directory=system_fs_directory,
                replacements=replacements,
            )

            _trim_empty_directories(fs_dir)

            # Document the files and directories:
            trace(f"Temporary directory: {fs_dir}...")
            for root, _, files in os.walk(fs_dir):
                trace(f"+ {root}")
                for f in files:
                    trace(f"|  + {f}")

            # Package up the initrd:
            run(
                "/usr/bin/sh",
                "-c",
                f'"{self._binary(Binaries.FIND)}" . | "{self._binary(Binaries.CPIO)}" -o -H newc | gzip > "{initrd}"',
                work_directory=fs_dir,
                returncode=0,
            )

        trace("Extra initrd created.")

    def __call__(
        self,
        location: Location,
        system_context: SystemContext,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        """Execute command."""

        # scan for the modules!
        if not _modules:
            _populate_modules(system_context.fs_directory)
            assert _modules

        if not os.path.exists(os.path.join(system_context.boot_directory, "vmlinuz")):
            info("Skipping clrm initrd extra generation: No vmlinuz in boot directory.")
            return

        self._vg = system_context.substitution_expanded("DEFAULT_VG", "")
        self._image_fs = system_context.substitution_expanded("IMAGE_FS", "")
        self._image_device = _device_ify(
            system_context.substitution_expanded("IMAGE_DEVICE", "")
        )
        self._image_options = system_context.substitution_expanded("IMAGE_OPTIONS", "")

        image_name = system_context.substitution_expanded("CLRM_IMAGE_FILENAME", "")
        self._full_name = image_name

        initrd = args[0]

        helper_dir = self._helper_directory
        assert helper_dir

        trace(f"Looking for clrm initrd configuration in {helper_dir}.")

        image_base_name = self._full_name
        pos = image_base_name.find(".")
        if pos >= 0:
            image_base_name = image_base_name[:pos]

        replacements: typing.Dict[str, typing.Optional[str]] = {
            "image_device": self._image_device if self._image_device else None,
            "escaped_image_device": _escape_device(self._image_device)
            if self._image_device
            else None,
            "image_fs": self._image_fs if self._image_fs else None,
            "image_options": self._image_options,  # These may be empty!
            "volume_group": self._vg if self._vg else None,
            "image_full_name": self._full_name,
            "image_base_name": image_base_name,
        }

        for k, v in replacements.items():
            trace(f'Set up replacement: {k} -> {"<NONE>" if v is None else v}...')

        self._create_initrd(
            initrd,
            helper_dir=helper_dir,
            system_fs_directory=system_context.fs_directory,
            replacements=replacements,
        )

        modules = (
            system_context.substitution("INITRD_EXTRA_MODULES", "").split(" ")
            + _extra_modules
        )
        system_context.set_substitution("INITRD_EXTRA_MODULES", " ".join(modules))

        trace("Done with extra initrd creation.")
        assert os.path.isfile(initrd)
