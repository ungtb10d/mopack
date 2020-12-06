import shutil

from . import Builder, BuilderOptions
from .. import types
from ..log import LogFile
from ..path import pushd
from ..usage import make_usage

_known_install_types = ('prefix', 'exec-prefix', 'bindir', 'libdir',
                        'includedir')


class Bfg9000Builder(Builder):
    type = 'bfg9000'

    class Options(BuilderOptions):
        type = 'bfg9000'

        def __init__(self):
            self.toolchain = types.Unset

        def __call__(self, *, toolchain=types.Unset, config_file=None,
                     child_config=False):
            if not child_config and self.toolchain is types.Unset:
                self.toolchain = toolchain

    def __init__(self, name, *, extra_args=None, usage=None, submodules,
                 _options, **kwargs):
        if usage is None:
            usage = make_usage(name, 'pkg-config', submodules=submodules,
                               _options=_options)
        super().__init__(name, usage=usage, _options=_options, **kwargs)
        self.extra_args = types.shell_args()('extra_args', extra_args)

    def _toolchain_args(self, toolchain):
        return ['--toolchain', toolchain] if toolchain else []

    def _install_args(self, deploy_paths):
        args = []
        for k, v in deploy_paths.items():
            if k in _known_install_types:
                args.extend(['--' + k, v])
        return args

    def clean(self, pkgdir):
        shutil.rmtree(self._builddir(pkgdir), ignore_errors=True)

    def build(self, pkgdir, srcdir, deploy_paths={}):
        builddir = self._builddir(pkgdir)

        with LogFile.open(pkgdir, self.name) as logfile:
            with pushd(srcdir):
                logfile.check_call(
                    ['9k', builddir] +
                    self._toolchain_args(self._this_options.toolchain) +
                    self._install_args(deploy_paths) +
                    self.extra_args
                )
            with pushd(builddir):
                logfile.check_call(['ninja'])

    def deploy(self, pkgdir):
        with LogFile.open(pkgdir, self.name, kind='deploy') as logfile:
            with pushd(self._builddir(pkgdir)):
                logfile.check_call(['ninja', 'install'])
