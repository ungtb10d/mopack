import os
import subprocess
from unittest import mock

from . import BuilderTest
from .. import mock_open_log

from mopack.builders import Builder
from mopack.builders.cmake import CMakeBuilder
from mopack.iterutils import iterate
from mopack.usage import make_usage
from mopack.usage.pkg_config import PkgConfigUsage


class TestCMakeBuilder(BuilderTest):
    builder_type = CMakeBuilder
    pkgdir = os.path.abspath('/path/to/builddir/mopack')

    def pkgconfdir(self, name, pkgconfig='pkgconfig'):
        return os.path.join(self.pkgdir, 'build', name, pkgconfig)

    def check_build(self, builder, deploy_paths={}, extra_args=[], *,
                    submodules=None, usage=None):
        if usage is None:
            pcfiles = ['foo']
            pcfiles.extend('foo_{}'.format(i) for i in iterate(submodules))
            usage = {'type': 'pkg-config', 'path': self.pkgconfdir('foo'),
                     'pcfiles': pcfiles, 'extra_args': []}

        srcdir = '/path/to/src'
        with mock_open_log() as mopen, \
             mock.patch('mopack.builders.cmake.pushd'), \
             mock.patch('subprocess.run') as mcall:  # noqa
            builder.build(self.pkgdir, srcdir, deploy_paths)
            mopen.assert_called_with(os.path.join(
                self.pkgdir, 'logs', 'foo.log'
            ), 'a')
            mcall.assert_any_call(
                ['cmake', srcdir, '-G', 'Ninja'] + extra_args,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, check=True
            )
            mcall.assert_called_with(
                ['ninja'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, check=True
            )
        self.assertEqual(builder.get_usage(self.pkgdir, submodules, srcdir),
                         usage)

    def test_basic(self):
        builder = self.make_builder('foo', usage='pkg-config')
        self.assertEqual(builder.name, 'foo')
        self.assertEqual(builder.extra_args, [])
        self.assertEqual(builder.usage, PkgConfigUsage(
            'foo', submodules=None, _options=self.make_options()
        ))

        self.check_build(builder)

        with mock_open_log() as mopen, \
             mock.patch('mopack.builders.cmake.pushd'), \
             mock.patch('subprocess.run') as mcall:  # noqa
            builder.deploy(self.pkgdir)
            mopen.assert_called_with(os.path.join(
                self.pkgdir, 'logs', 'deploy', 'foo.log'
            ), 'a')
            mcall.assert_called_with(
                ['ninja', 'install'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, check=True
            )

    def test_extra_args(self):
        builder = self.make_builder('foo', extra_args='--extra args',
                                    usage='pkg-config')
        self.assertEqual(builder.name, 'foo')
        self.assertEqual(builder.extra_args, ['--extra', 'args'])
        self.assertEqual(builder.usage, PkgConfigUsage(
            'foo', submodules=None, _options=self.make_options()
        ))

        self.check_build(builder, extra_args=['--extra', 'args'])

    def test_usage_full(self):
        usage = {'type': 'pkg-config', 'path': 'pkgconf'}
        builder = self.make_builder('foo', usage=usage)
        self.assertEqual(builder.name, 'foo')
        self.assertEqual(builder.extra_args, [])
        self.assertEqual(builder.usage, PkgConfigUsage(
            'foo', path='pkgconf', submodules=None,
            _options=self.make_options()
        ))

        self.check_build(builder, usage={
            'type': 'pkg-config', 'path': self.pkgconfdir('foo', 'pkgconf'),
            'pcfiles': ['foo'], 'extra_args': [],
        })

    def test_submodules(self):
        submodules_required = {'names': '*', 'required': True}
        submodules_optional = {'names': '*', 'required': False}

        builder = self.make_builder('foo', usage='pkg-config',
                                    submodules=submodules_required)
        self.check_build(builder, submodules=['sub'], usage={
            'type': 'pkg-config', 'path': self.pkgconfdir('foo'),
            'pcfiles': ['foo_sub'], 'extra_args': [],
        })

        builder = self.make_builder(
            'foo', usage={'type': 'pkg-config', 'pcfile': 'bar'},
            submodules=submodules_required
        )
        self.check_build(builder, submodules=['sub'], usage={
            'type': 'pkg-config', 'path': self.pkgconfdir('foo'),
            'pcfiles': ['bar', 'foo_sub'], 'extra_args': [],
        })

        builder = self.make_builder('foo', usage='pkg-config',
                                    submodules=submodules_optional)
        self.check_build(builder, submodules=['sub'])

        builder = self.make_builder(
            'foo', usage={'type': 'pkg-config', 'pcfile': 'bar'},
            submodules=submodules_optional
        )
        self.check_build(builder, submodules=['sub'], usage={
            'type': 'pkg-config', 'path': self.pkgconfdir('foo'),
            'pcfiles': ['bar', 'foo_sub'], 'extra_args': [],
        })

    def test_deploy_paths(self):
        deploy_paths = {'prefix': '/usr/local', 'goofy': '/foo/bar'}
        builder = self.make_builder('foo', usage='pkg-config')
        self.assertEqual(builder.name, 'foo')
        self.assertEqual(builder.extra_args, [])
        self.assertEqual(builder.usage, PkgConfigUsage(
            'foo', submodules=None, _options=self.make_options()
        ))

        self.check_build(builder, deploy_paths, extra_args=[
            '-DCMAKE_INSTALL_PREFIX:PATH=' + os.path.abspath('/usr/local')
        ])

    def test_clean(self):
        builder = self.make_builder('foo', usage='pkg-config')
        srcdir = os.path.join(self.pkgdir, 'build', 'foo')

        with mock.patch('shutil.rmtree') as mrmtree:
            builder.clean(self.pkgdir)
            mrmtree.assert_called_once_with(srcdir, ignore_errors=True)

    def test_rehydrate(self):
        opts = self.make_options()
        usage = make_usage('foo', {'type': 'pkg-config', 'path': 'pkgconf'},
                           submodules=None, _options=opts)
        builder = CMakeBuilder('foo', extra_args='--extra args', usage=usage,
                               submodules=None, _options=opts)
        data = builder.dehydrate()
        self.assertEqual(builder, Builder.rehydrate(data, _options=opts))
