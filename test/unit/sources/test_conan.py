import os
import subprocess
from io import StringIO
from textwrap import dedent
from unittest import mock

from . import OptionsTest, SourceTest, through_json
from .. import mock_open_log

from mopack.iterutils import iterate
from mopack.shell import ShellArguments
from mopack.sources import Package, PackageOptions
from mopack.sources.apt import AptPackage
from mopack.sources.conan import ConanPackage
from mopack.types import dependency_string


def mock_open_write():
    class MockFile(StringIO):
        def close(self):
            pass

    mock_open = mock.mock_open()

    def non_mock(*args, **kwargs):
        mock_open.side_effect = None
        mock_open.mock_file = MockFile()
        return mock_open.mock_file

    mock_open.side_effect = non_mock
    return mock_open


class TestConan(SourceTest):
    pkg_type = ConanPackage
    config_file = os.path.abspath('/path/to/mopack.yml')
    pkgdir = os.path.abspath('/path/to/builddir/mopack')
    pkgconfdir = os.path.join(pkgdir, 'conan')

    def check_resolve_all(self, pkgs, conanfile, extra_args=[]):
        with mock_open_log(mock_open_write()) as mopen, \
             mock.patch('subprocess.run') as mrun:
            ConanPackage.resolve_all(pkgs, self.pkgdir)

            self.assertEqual(mopen.mock_file.getvalue(), conanfile)
            conandir = os.path.join(self.pkgdir, 'conan')
            mrun.assert_called_with(
                (['conan', 'install', '-if', conandir] + extra_args +
                 ['--', self.pkgdir]),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, check=True
            )

    def check_usage(self, pkg, *, submodules=None, usage=None):
        if usage is None:
            pcfiles = ([] if pkg.submodules and pkg.submodules['required'] else
                       [pkg.name])
            pcfiles.extend('{}_{}'.format(pkg.name, i)
                           for i in iterate(submodules))
            usage = {'name': dependency_string(pkg.name, submodules),
                     'type': 'pkg_config', 'path': [self.pkgconfdir],
                     'pcfiles': pcfiles, 'extra_args': []}
        self.assertEqual(pkg.get_usage(submodules, self.pkgdir), usage)

    def test_basic(self):
        pkg = self.make_package('foo', remote='foo/1.2.3@conan/stable')
        self.assertEqual(pkg.remote, 'foo/1.2.3@conan/stable')
        self.assertEqual(pkg.build, False)
        self.assertEqual(pkg.options, {})
        self.assertEqual(pkg.needs_dependencies, False)
        self.assertEqual(pkg.should_deploy, True)

        self.check_resolve_all([pkg], dedent("""\
            [requires]
            foo/1.2.3@conan/stable

            [options]

            [generators]
            pkg_config
        """))

        with mock.patch('subprocess.run') as mrun:
            pkg.version(self.pkgdir)
            mrun.assert_called_once_with(
                ['conan', 'inspect', '--raw=version',
                 'foo/1.2.3@conan/stable'],
                check=True, stdout=subprocess.PIPE, universal_newlines=True
            )

        self.check_usage(pkg)

    def test_build(self):
        pkg = self.make_package('foo', remote='foo/1.2.3@conan/stable',
                                build=True)
        self.assertEqual(pkg.remote, 'foo/1.2.3@conan/stable')
        self.assertEqual(pkg.build, True)
        self.assertEqual(pkg.options, {})
        self.assertEqual(pkg.needs_dependencies, False)
        self.assertEqual(pkg.should_deploy, True)

        self.check_resolve_all([pkg], dedent("""\
            [requires]
            foo/1.2.3@conan/stable

            [options]

            [generators]
            pkg_config
        """), ['--build=foo'])

        self.check_usage(pkg)

    def test_options(self):
        pkg = self.make_package('foo', remote='foo/1.2.3@conan/stable',
                                options={'shared': True})
        self.assertEqual(pkg.remote, 'foo/1.2.3@conan/stable')
        self.assertEqual(pkg.build, False)
        self.assertEqual(pkg.options, {'shared': True})
        self.assertEqual(pkg.should_deploy, True)

        self.check_resolve_all([pkg], dedent("""\
            [requires]
            foo/1.2.3@conan/stable

            [options]
            foo:shared=True

            [generators]
            pkg_config
        """))

        self.check_usage(pkg)

    def test_this_options(self):
        pkg = self.make_package('foo', remote='foo/1.2.3@conan/stable',
                                this_options={'build': 'foo',
                                              'extra_args': '-gcmake'})
        self.assertEqual(pkg.remote, 'foo/1.2.3@conan/stable')
        self.assertEqual(pkg.build, False)
        self.assertEqual(pkg.options, {})
        self.assertEqual(pkg.should_deploy, True)

        self.check_resolve_all([pkg], dedent("""\
            [requires]
            foo/1.2.3@conan/stable

            [options]

            [generators]
            pkg_config
        """), ['--build=foo', '-gcmake'])

        self.check_usage(pkg)

    def test_this_options_build_all(self):
        pkg = self.make_package('foo', remote='foo/1.2.3@conan/stable',
                                this_options={'build': 'all'})
        self.assertEqual(pkg.remote, 'foo/1.2.3@conan/stable')
        self.assertEqual(pkg.build, False)
        self.assertEqual(pkg.options, {})
        self.assertEqual(pkg.should_deploy, True)

        self.check_resolve_all([pkg], dedent("""\
            [requires]
            foo/1.2.3@conan/stable

            [options]

            [generators]
            pkg_config
        """), ['--build'])

        self.check_usage(pkg)

    def test_this_options_merge_build(self):
        pkg = self.make_package(
            'foo', remote='foo/1.2.3@conan/stable', build=True,
            this_options={'build': ['foo', 'bar']}
        )
        self.assertEqual(pkg.remote, 'foo/1.2.3@conan/stable')
        self.assertEqual(pkg.build, True)
        self.assertEqual(pkg.options, {})
        self.assertEqual(pkg.should_deploy, True)

        self.check_resolve_all([pkg], dedent("""\
            [requires]
            foo/1.2.3@conan/stable

            [options]

            [generators]
            pkg_config
        """), ['--build=foo', '--build=bar'])

        self.check_usage(pkg)

    def test_multiple(self):
        pkgs = [
            self.make_package('foo', remote='foo/1.2.3@conan/stable'),
            self.make_package('bar', remote='bar/2.3.4@conan/stable',
                              options={'shared': True}),
        ]

        self.check_resolve_all(pkgs, dedent("""\
                [requires]
                foo/1.2.3@conan/stable
                bar/2.3.4@conan/stable

                [options]
                bar:shared=True

                [generators]
                pkg_config
            """))

        for pkg in pkgs:
            self.check_usage(pkg)

    def test_submodules(self):
        submodules_required = {'names': '*', 'required': True}
        submodules_optional = {'names': '*', 'required': False}

        pkg = self.make_package('foo', remote='foo/1.2.3@conan/stable',
                                submodules=submodules_required)
        self.check_usage(pkg, submodules=['sub'])

        pkg = self.make_package('foo', remote='foo/1.2.3@conan/stable',
                                usage={'type': 'pkg_config', 'path': '.',
                                       'pcfile': 'bar'},
                                submodules=submodules_required)
        self.check_usage(pkg, submodules=['sub'], usage={
            'name': 'foo[sub]', 'type': 'pkg_config',
            'path': [self.pkgconfdir], 'pcfiles': ['bar', 'foo_sub'],
            'extra_args': [],
        })

        pkg = self.make_package('foo', remote='foo/1.2.3@conan/stable',
                                submodules=submodules_optional)
        self.check_usage(pkg, submodules=['sub'])

        pkg = self.make_package('foo', remote='foo/1.2.3@conan/stable',
                                usage={'type': 'pkg_config', 'path': '.',
                                       'pcfile': 'bar'},
                                submodules=submodules_optional)
        self.check_usage(pkg, submodules=['sub'], usage={
            'name': 'foo[sub]', 'type': 'pkg_config',
            'path': [self.pkgconfdir], 'pcfiles': ['bar', 'foo_sub'],
            'extra_args': [],
        })

    def test_invalid_submodule(self):
        pkg = self.make_package(
            'foo', remote='foo/1.2.3@conan/stable',
            submodules={'names': ['sub'], 'required': True}
        )
        with self.assertRaises(ValueError):
            pkg.get_usage(['invalid'], self.pkgdir)

    def test_deploy(self):
        pkg = self.make_package('foo', remote='foo/1.2.3@conan/stable')
        self.assertEqual(pkg.should_deploy, True)
        with mock.patch('warnings.warn') as mwarn:
            ConanPackage.deploy_all([pkg], self.pkgdir)
            mwarn.assert_called_once()

        pkg = self.make_package('foo', remote='foo/1.2.3@conan/stable',
                                deploy=False)
        self.assertEqual(pkg.should_deploy, False)
        with mock.patch('warnings.warn') as mwarn:
            ConanPackage.deploy_all([pkg], self.pkgdir)
            mwarn.assert_not_called()

    def test_clean_pre(self):
        oldpkg = self.make_package('foo', remote='foo/1.2.3@conan/stable')
        newpkg = self.make_package(AptPackage, 'foo')

        # Conan -> Apt
        self.assertEqual(oldpkg.clean_pre(newpkg, self.pkgdir), False)

        # Conan -> Nothing
        self.assertEqual(oldpkg.clean_pre(None, self.pkgdir), False)

    def test_clean_post(self):
        oldpkg = self.make_package('foo', remote='foo/1.2.3@conan/stable')
        newpkg1 = self.make_package('foo', remote='foo/1.2.4@conan/stable')
        newpkg2 = self.make_package(AptPackage, 'foo')

        # Conan -> Conan
        with mock.patch('mopack.log.pkg_clean') as mlog, \
             mock.patch('os.remove') as mremove:
            self.assertEqual(oldpkg.clean_post(newpkg1, self.pkgdir), False)
            mlog.assert_not_called()
            mremove.assert_not_called()

        # Conan -> Apt
        with mock.patch('mopack.log.pkg_clean') as mlog, \
             mock.patch('os.remove') as mremove:
            self.assertEqual(oldpkg.clean_post(newpkg2, self.pkgdir), True)
            mlog.assert_called_once()
            mremove.assert_called_once_with(os.path.join(
                self.pkgdir, 'conan', 'foo.pc'
            ))

        # Conan -> nothing
        with mock.patch('mopack.log.pkg_clean') as mlog, \
             mock.patch('os.remove') as mremove:
            self.assertEqual(oldpkg.clean_post(None, self.pkgdir), True)
            mlog.assert_called_once()
            mremove.assert_called_once_with(os.path.join(
                self.pkgdir, 'conan', 'foo.pc'
            ))

        # Conan -> nothing (quiet)
        with mock.patch('mopack.log.pkg_clean') as mlog, \
             mock.patch('os.remove') as mremove:
            self.assertEqual(oldpkg.clean_post(None, self.pkgdir, True), True)
            mlog.assert_not_called()
            mremove.assert_called_once_with(os.path.join(
                self.pkgdir, 'conan', 'foo.pc'
            ))

        # Error deleting
        with mock.patch('mopack.log.pkg_clean') as mlog, \
             mock.patch('os.remove', side_effect=FileNotFoundError) as mremove:
            self.assertEqual(oldpkg.clean_post(None, self.pkgdir), True)
            mlog.assert_called_once()
            mremove.assert_called_once_with(os.path.join(
                self.pkgdir, 'conan', 'foo.pc'
            ))

    def test_clean_all(self):
        oldpkg = self.make_package('foo', remote='foo/1.2.3@conan/stable')
        newpkg1 = self.make_package('foo', remote='foo/1.2.4@conan/stable')
        newpkg2 = self.make_package(AptPackage, 'foo')

        # Conan -> Conan
        with mock.patch('mopack.log.pkg_clean') as mlog, \
             mock.patch('os.remove') as mremove:
            self.assertEqual(oldpkg.clean_all(newpkg1, self.pkgdir),
                             (False, False))
            mlog.assert_not_called()
            mremove.assert_not_called()

        # Conan -> Apt
        with mock.patch('mopack.log.pkg_clean') as mlog, \
             mock.patch('os.remove') as mremove:
            self.assertEqual(oldpkg.clean_all(newpkg2, self.pkgdir),
                             (False, True))
            mlog.assert_called_once()
            mremove.assert_called_once_with(os.path.join(
                self.pkgdir, 'conan', 'foo.pc'
            ))

        # Conan -> nothing
        with mock.patch('mopack.log.pkg_clean') as mlog, \
             mock.patch('os.remove') as mremove:
            self.assertEqual(oldpkg.clean_all(None, self.pkgdir),
                             (False, True))
            mlog.assert_called_once()
            mremove.assert_called_once_with(os.path.join(
                self.pkgdir, 'conan', 'foo.pc'
            ))

        # Error deleting
        with mock.patch('mopack.log.pkg_clean') as mlog, \
             mock.patch('os.remove', side_effect=FileNotFoundError) as mremove:
            self.assertEqual(oldpkg.clean_all(None, self.pkgdir),
                             (False, True))
            mlog.assert_called_once()
            mremove.assert_called_once_with(os.path.join(
                self.pkgdir, 'conan', 'foo.pc'
            ))

    def test_equality(self):
        remote = 'foo/1.2.3@conan/stable'
        options = {'shared': True}
        pkg = self.make_package('foo', remote=remote, options=options)

        self.assertEqual(pkg, self.make_package(
            'foo', remote=remote, options=options
        ))
        self.assertEqual(pkg, self.make_package(
            'foo', remote=remote, options=options,
            config_file='/path/to/mopack2.yml'
        ))

        self.assertNotEqual(pkg, self.make_package(
            'bar', remote=remote, options=options
        ))
        self.assertNotEqual(pkg, self.make_package(
            'foo', remote='foo/1.2.4@conan/stable', options=options
        ))
        self.assertNotEqual(pkg, self.make_package('foo', remote=remote))

    def test_rehydrate(self):
        opts = self.make_options()
        pkg = ConanPackage('foo', remote='foo/1.2.3@conan/stable',
                           options={'shared': True}, _options=opts,
                           config_file=self.config_file)
        data = through_json(pkg.dehydrate())
        self.assertEqual(pkg, Package.rehydrate(data, _options=opts))

    def test_upgrade(self):
        opts = self.make_options()
        data = {'source': 'conan', '_version': 0, 'name': 'foo',
                'remote': 'foo', 'build': False, 'options': None,
                'usage': {'type': 'system', '_version': 0}}
        with mock.patch.object(ConanPackage, 'upgrade',
                               side_effect=ConanPackage.upgrade) as m:
            pkg = Package.rehydrate(data, _options=opts)
            self.assertIsInstance(pkg, ConanPackage)
            m.assert_called_once()


class TestConanOptions(OptionsTest):
    symbols = {'variable': 'value'}

    def test_default(self):
        opts = ConanPackage.Options()
        self.assertEqual(opts.build, [])
        self.assertEqual(opts.extra_args, ShellArguments())

    def test_build(self):
        opts = ConanPackage.Options()
        opts(build='foo', config_file=self.config_file, _symbols=self.symbols)
        self.assertEqual(opts.build, ['foo'])

        opts(build=['bar', 'foo', 'baz'], config_file=self.config_file,
             _symbols=self.symbols)
        self.assertEqual(opts.build, ['foo', 'bar', 'baz'])

        opts(build='$variable', config_file=self.config_file,
             _symbols=self.symbols)
        self.assertEqual(opts.build, ['foo', 'bar', 'baz', 'value'])

    def test_extra_args(self):
        opts = ConanPackage.Options()
        opts(extra_args='--foo', config_file=self.config_file,
             _symbols=self.symbols)
        self.assertEqual(opts.extra_args, ShellArguments(['--foo']))

        opts(extra_args='--bar --baz', config_file=self.config_file,
             _symbols=self.symbols)
        self.assertEqual(opts.extra_args, ShellArguments([
            '--foo', '--bar', '--baz'
        ]))

        opts(extra_args=['--goat', '--panda'], config_file=self.config_file,
             _symbols=self.symbols)
        self.assertEqual(opts.extra_args, ShellArguments([
            '--foo', '--bar', '--baz', '--goat', '--panda'
        ]))

        opts(extra_args='$variable', config_file=self.config_file,
             _symbols=self.symbols)
        self.assertEqual(opts.extra_args, ShellArguments([
            '--foo', '--bar', '--baz', '--goat', '--panda', 'value'
        ]))

    def test_rehydrate(self):
        opts = ConanPackage.Options()
        opts(build='foo', extra_args='--arg', config_file=self.config_file,
             _symbols=self.symbols)
        data = through_json(opts.dehydrate())
        self.assertEqual(opts, PackageOptions.rehydrate(data))

    def test_upgrade(self):
        data = {'source': 'conan', '_version': 0, 'build': [],
                'extra_args': []}
        with mock.patch.object(ConanPackage.Options, 'upgrade',
                               side_effect=ConanPackage.Options.upgrade) as m:
            pkg = PackageOptions.rehydrate(data)
            self.assertIsInstance(pkg, ConanPackage.Options)
            m.assert_called_once()
