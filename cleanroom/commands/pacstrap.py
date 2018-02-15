"""pacstrap command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


import cleanroom.command as cmd
import cleanroom.context as context
import cleanroom.execobject as eo
import cleanroom.exceptions as ex
import cleanroom.helper.archlinux.pacman as pacman
import cleanroom.helper.generic.file as file
import cleanroom.parser as parser
import cleanroom.run as run


class PacstrapCommand(cmd.Command):
    """The pacstrap command."""

    def __init__(self):
        """Constructor."""
        super().__init__('pacstrap <PACKAGES> config=<CONFIG_FILE>',
                         'Run pacstrap to install <PACKAGES>.')

    def validate_arguments(self, file_name, line_number, *args, **kwargs):
        """Validate the arguments."""
        if len(args) < 1:
            raise ex.ParseError(file_name, line_number,
                                'pacstrap needs at least '
                                'one package or group to install.')

        if 'config' not in kwargs:
            raise ex.ParseError(file_name, line_number,
                                'pacstrap needs a "config" keyword argument.')
        return None

    def __call__(self, run_context, *args, **kwargs):
        """Execute command."""
        pac_object = pacman.Pacman(run_context)

        pacstrap_config = kwargs['config']
        self._prepare_keyring(run_context, pac_object, pacstrap_config)

        pac_object.pacstrap(pacstrap_config, args)

    def _prepare_keyring(self, run_context, pac_object, pacstrap_config):
        # Make sure important pacman directories exist:
        file.makedirs(run_context, pac_object.host_gpg_directory())
        pacman_key = run_context.ctx.binary(context.Binaries.PACMAN_KEY)
        run.run(pacman_key,
                '--config', pacstrap_config,
                '--gpgdir', pac_object.host_gpg_directory(),
                '--init',
                exit_code=0,
                work_directory=run_context.ctx.systems_directory(),
                trace_output=run_context.ctx.printer.trace)
        run.run(pacman_key,
                '--config', pacstrap_config,
                '--gpgdir', pac_object.host_gpg_directory(),
                '--populate', 'archlinux',
                exit_code=0,
                work_directory=run_context.ctx.systems_directory(),
                trace_output=run_context.ctx.printer.trace)

        gpgdir = pac_object.target_gpg_directory()
        packageFiles = pac_object.target_cache_directory() + '/pkg/*'

        run_context.add_hook('_teardown',
                             eo.ExecObject(('<pacstrap command>', 1),
                                           'garbage collect pacman files',
                                           None,
                                           parser.Parser.command('remove'),
                                           gpgdir + '/S.*',
                                           gpgdir + '/pubring.gpg~',
                                           '/var/log/pacman.log',
                                           packageFiles,
                                           force=True, recursive=True))

        run_context.add_hook('export',
                             eo.ExecObject(('<pacstrap command>', 2),
                                           'remove pacman secret keys',
                                           None,
                                           parser.Parser.command('remove'),
                                           gpgdir + '/secring.gpg*',
                                           force=True))
