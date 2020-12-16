import json
import os

from mopack.path import pushd
from mopack.platforms import platform_name

from . import *


class TestNested(IntegrationTest):
    def setUp(self):
        self.stage = stage_dir('nested')
        self.prefix = stage_dir('nested-install', chdir=False)
        self.pkgbuilddir = os.path.join(self.stage, 'mopack', 'build')

    def check_usage(self, name):
        output = json.loads(self.assertPopen([
            'mopack', 'usage', name, '--json'
        ]))
        self.assertEqual(output, {
            'name': name,
            'type': 'pkg-config',
            'path': os.path.join(self.pkgbuilddir, name, 'pkgconfig'),
            'pcfiles': [name],
            'extra_args': [],
        })

    def _builder(self, name):
        return {
            'type': 'bfg9000',
            'name': name,
            'extra_args': [],
            'usage': {
                'type': 'pkg-config',
                'path': ['builddir', 'pkgconfig'],
                'pcfile': name,
                'extra_args': [],
            },
        }

    def test_resolve(self):
        config = os.path.join(test_data_dir, 'mopack-nested.yml')
        self.assertPopen(['mopack', 'resolve', config,
                          '-Pprefix=' + self.prefix])
        self.assertExists('mopack/build/greeter/')
        self.assertExists('mopack/logs/greeter.log')
        self.assertExists('mopack/src/hello/hello-bfg/')
        self.assertExists('mopack/build/hello/')
        self.assertExists('mopack/logs/hello.log')
        self.assertExists('mopack/mopack.json')

        self.check_usage('greeter')
        self.check_usage('hello')

        output = json.loads(slurp('mopack/mopack.json'))
        self.assertEqual(output['metadata'], {
            'options': {
                'common': {
                    'target_platform': platform_name(),
                    'env': AlwaysEqual(),
                    'deploy_paths': {'prefix': self.prefix},
                },
                'builders': [{
                    'type': 'bfg9000',
                    'toolchain': None,
                }],
                'sources': [],
            },
            'packages': [{
                'name': 'hello',
                'config_file': os.path.join(test_data_dir, 'greeter-bfg',
                                            'mopack.yml'),
                'resolved': True,
                'source': 'tarball',
                'submodules': None,
                'should_deploy': True,
                'builder': self._builder('hello'),
                'url': None,
                'path': ['cfgdir', os.path.join('..', 'hello-bfg.tar.gz')],
                'files': [],
                'srcdir': None,
                'guessed_srcdir': 'hello-bfg',
                'patch': None,
            }, {
                'name': 'greeter',
                'config_file': config,
                'resolved': True,
                'source': 'directory',
                'submodules': None,
                'should_deploy': True,
                'builder': self._builder('greeter'),
                'path': ['cfgdir', 'greeter-bfg'],
            }],
        })

        self.assertPopen(['mopack', 'deploy'])
        include_prefix = '' if platform_name() == 'windows' else 'include/'
        lib_prefix = '' if platform_name() == 'windows' else 'lib/'
        with pushd(self.prefix):
            self.assertExists(include_prefix + 'greeter.hpp')
            self.assertExists(lib_prefix + 'pkgconfig/greeter.pc')
            self.assertExists(include_prefix + 'hello.hpp')
            self.assertExists(lib_prefix + 'pkgconfig/hello.pc')
