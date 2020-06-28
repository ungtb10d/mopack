import json
import os

from mopack.path import pushd
from mopack.platforms import platform_name

from . import *


class SDistTest(IntegrationTest):
    def _check_usage(self, name):
        output = json.loads(self.assertPopen([
            'mopack', 'usage', name, '--json'
        ]))
        self.assertEqual(output, {
            'name': name,
            'type': 'pkg-config',
            'path': os.path.join(self.stage, 'mopack', 'build', name,
                                 'pkgconfig'),
            'pcfiles': [name],
        })

    def _options(self):
        return {
            'common': {'target_platform': platform_name()},
            'builders': [{
                'type': 'bfg9000',
                'toolchain': None,
            }],
            'sources': [],
        }

    def _builder(self, name):
        return {
            'type': 'bfg9000',
            'name': name,
            'extra_args': [],
            'usage': {
                'type': 'pkg-config',
                'path': 'pkgconfig',
                'pcfile': name,
            },
        }


class TestDirectory(SDistTest):
    def setUp(self):
        self.stage = stage_dir('directory')

    def test_resolve(self):
        config = os.path.join(test_data_dir, 'mopack-directory-implicit.yml')
        self.assertPopen(['mopack', 'resolve', config])
        self.assertNotExists('mopack/src/hello/hello-bfg/build.bfg')
        self.assertExists('mopack/build/hello/')
        self.assertExists('mopack/hello.log')
        self.assertExists('mopack/mopack.json')

        self._check_usage('hello')

        output = json.loads(slurp('mopack/mopack.json'))
        self.assertEqual(output['metadata'], {
            'deploy_paths': {},
            'options': self._options(),
            'packages': [{
                'name': 'hello',
                'config_file': config,
                'source': 'directory',
                'submodules': None,
                'builder': self._builder('hello'),
                'path': os.path.join(test_data_dir, 'hello-bfg'),
            }],
        })


class TestTarball(SDistTest):
    def setUp(self):
        self.stage = stage_dir('tarball')
        self.prefix = stage_dir('tarball-install', chdir=False)

    def test_resolve(self):
        config = os.path.join(test_data_dir, 'mopack-tarball.yml')
        self.assertPopen(['mopack', 'resolve', config,
                          '-Pprefix=' + self.prefix])
        self.assertExists('mopack/src/hello/hello-bfg/build.bfg')
        self.assertExists('mopack/build/hello/')
        self.assertExists('mopack/hello.log')
        self.assertExists('mopack/mopack.json')

        self._check_usage('hello')

        output = json.loads(slurp('mopack/mopack.json'))
        self.assertEqual(output['metadata'], {
            'deploy_paths': {'prefix': self.prefix},
            'options': self._options(),
            'packages': [{
                'name': 'hello',
                'config_file': config,
                'source': 'tarball',
                'submodules': None,
                'builder': self._builder('hello'),
                'url': None,
                'path': os.path.join(test_data_dir, 'hello-bfg.tar.gz'),
                'srcdir': None,
                'guessed_srcdir': 'hello-bfg',
                'patch': None,
            }],
        })

        self.assertPopen(['mopack', 'deploy'])
        include_prefix = '' if platform_name() == 'windows' else 'include/'
        lib_prefix = '' if platform_name() == 'windows' else 'lib/'
        with pushd(self.prefix):
            self.assertExists(include_prefix + 'hello.hpp')
            self.assertExists(lib_prefix + 'pkgconfig/hello.pc')
