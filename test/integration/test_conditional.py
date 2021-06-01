import json
import os

from mopack.platforms import platform_name

from . import *


class TestConditional(IntegrationTest):
    name = 'conditional'

    def test_resolve(self):
        want_tarball = platform_name() == 'windows'

        config = os.path.join(test_data_dir, 'mopack-conditional.yml')
        self.assertPopen(['mopack', 'resolve', config])
        self.assertExistence('mopack/src/hello/hello-bfg/build.bfg',
                             want_tarball)
        self.assertExists('mopack/build/hello/')
        self.assertExists('mopack/logs/hello.log')
        self.assertExists('mopack/mopack.json')

        self.assertPkgConfigUsage('hello')

        output = json.loads(slurp('mopack/mopack.json'))
        if want_tarball:
            hellopkg = {
                'name': 'hello',
                'config_file': config,
                'resolved': True,
                'source': 'tarball',
                '_version': 1,
                'submodules': None,
                'should_deploy': True,
                'builder': cfg_bfg9000_builder('hello'),
                'url': None,
                'path': {'base': 'cfgdir', 'path': 'hello-bfg.tar.gz'},
                'files': [],
                'srcdir': None,
                'guessed_srcdir': 'hello-bfg',
                'patch': None,
            }
        else:
            hellopkg = {
                'name': 'hello',
                'config_file': config,
                'resolved': True,
                'source': 'directory',
                '_version': 1,
                'submodules': None,
                'should_deploy': True,
                'builder': cfg_bfg9000_builder('hello'),
                'path': {'base': 'cfgdir', 'path': 'hello-bfg'},
            }
        self.assertEqual(output['metadata'], {
            'options': cfg_options(bfg9000={}),
            'packages': [hellopkg],
        })