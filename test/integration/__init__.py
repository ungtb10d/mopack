import json
import os
import subprocess
import tempfile
import unittest
import yaml

from .. import *

from mopack.iterutils import listify
from mopack.platforms import platform_name
from mopack.types import dependency_string


# Also supported: 'apt', 'mingw-cross'
test_features = {'boost'}
for i in os.getenv('MOPACK_EXTRA_TESTS', '').split(' '):
    if i:
        test_features.add(i)
for i in os.getenv('MOPACK_SKIPPED_TESTS', '').split(' '):
    if i:
        test_features.remove(i)

# Get additional environment variables to use when getting usage. This
# is useful for setting things up to properly detect headers/libs for `path`
# usage.
usage_env = {}
try:
    test_env_file = os.path.join(test_dir, '../.mopack_test_env')
    with open(os.getenv('MOPACK_TEST_ENV_FILE', test_env_file)) as f:
        for line in f.readlines():
            k, v = line.rstrip('\n').split('=', 1)
            usage_env[k] = v
except FileNotFoundError:
    pass


def stage_dir(name, chdir=True):
    stage = tempfile.mkdtemp(prefix=name + '-', dir=test_stage_dir)
    if chdir:
        os.chdir(stage)
    return stage


def slurp(filename):
    with open(filename) as f:
        return f.read()


def cfg_common_options(target_platform=platform_name(), env=AlwaysEqual(),
                       deploy_paths={}):
    return {'_version': 1, 'target_platform': target_platform,
            'env': env, 'deploy_paths': deploy_paths}


def cfg_bfg9000_options(toolchain=None):
    return {'type': 'bfg9000', '_version': 1, 'toolchain': toolchain}


def cfg_cmake_options(toolchain=None):
    return {'type': 'cmake', '_version': 1, 'toolchain': toolchain}


def cfg_conan_options(build=[], extra_args=[]):
    return {'source': 'conan', '_version': 1, 'build': build,
            'extra_args': extra_args}


def cfg_options(**kwargs):
    result = {'common': cfg_common_options(**kwargs.pop('common', {})),
              'builders': [],
              'sources': []}
    for k, v in kwargs.items():
        opts = globals()['cfg_{}_options'.format(k)](**v)
        if k in ('bfg9000', 'cmake'):
            result['builders'].append(opts)
        else:
            result['sources'].append(opts)
    return result


def _cfg_package(source, api_version, name, config_file, parent=None,
                 resolved=True, submodules=None, should_deploy=True):
    return {
        'source': source,
        '_version': api_version,
        'name': name,
        'config_file': config_file,
        'parent': parent,
        'resolved': resolved,
        'submodules': submodules,
        'should_deploy': should_deploy,
    }


def cfg_directory_pkg(name, config_file, *, path, builder, **kwargs):
    result = _cfg_package('directory', 1, name, config_file, **kwargs)
    result.update({
        'path': path,
        'builder': builder,
    })
    return result


def cfg_tarball_pkg(name, config_file, *, path=None, url=None, files=[],
                    srcdir=None, guessed_srcdir=None, patch=None, builder,
                    **kwargs):
    result = _cfg_package('tarball', 1, name, config_file, **kwargs)
    result.update({
        'path': path,
        'url': url,
        'files': files,
        'srcdir': srcdir,
        'guessed_srcdir': guessed_srcdir,
        'patch': patch,
        'builder': builder,
    })
    return result


def cfg_git_pkg(name, config_file, *, repository, rev, srcdir='.', builder,
                **kwargs):
    result = _cfg_package('git', 1, name, config_file, **kwargs)
    result.update({
        'repository': repository,
        'rev': rev,
        'srcdir': srcdir,
        'builder': builder,
    })
    return result


def cfg_apt_pkg(name, config_file, *, remote, repository=None, usage,
                **kwargs):
    result = _cfg_package('apt', 1, name, config_file, **kwargs)
    result.update({
        'remote': remote,
        'repository': repository,
        'usage': usage,
    })
    return result


def cfg_conan_pkg(name, config_file, *, remote, build=False, options={}, usage,
                  **kwargs):
    result = _cfg_package('conan', 1, name, config_file, **kwargs)
    result.update({
        'remote': remote,
        'build': build,
        'options': options,
        'usage': usage,
    })
    return result


def cfg_bfg9000_builder(name, *, extra_args=[], usage=None):
    if usage is None:
        usage = cfg_pkg_config_usage(pcfile=name)
    return {
        'type': 'bfg9000',
        '_version': 1,
        'name': name,
        'extra_args': extra_args,
        'usage': usage
    }


def cfg_cmake_builder(name, *, extra_args=[], usage):
    return {
        'type': 'cmake',
        '_version': 1,
        'name': name,
        'extra_args': extra_args,
        'usage': usage
    }


def cfg_custom_builder(name, *, build_commands=[], deploy_commands=[],
                       usage):
    return {
        'type': 'custom',
        '_version': 1,
        'name': name,
        'build_commands': build_commands,
        'deploy_commands': deploy_commands,
        'usage': usage
    }


def cfg_pkg_config_usage(*, path=[{'base': 'builddir', 'path': 'pkgconfig'}],
                         pcfile, extra_args=[], **kwargs):
    return {
        'type': 'pkg_config',
        '_version': 1,
        'path': path,
        'pcfile': pcfile,
        'extra_args': extra_args,
        **kwargs
    }


def cfg_path_usage(*, auto_link=False, explicit_version=None, include_path=[],
                   library_path=[], headers=[], libraries=[], compile_flags=[],
                   link_flags=[], **kwargs):
    return {
        'type': 'path',
        '_version': 1,
        'auto_link': auto_link,
        'explicit_version': explicit_version,
        'include_path': include_path,
        'library_path': library_path,
        'headers': headers,
        'libraries': libraries,
        'compile_flags': compile_flags,
        'link_flags': link_flags,
        **kwargs
    }


def cfg_system_usage(*, pcfile=None, **kwargs):
    result = cfg_path_usage(**kwargs)
    result.update({
        'type': 'system',
        'pcfile': pcfile
    })
    return result


class SubprocessError(unittest.TestCase.failureException):
    def __init__(self, returncode, env, message):
        envstr = ''.join('  {} = {}\n'.format(k, v)
                         for k, v in (env or {}).items())
        msg = 'returned {returncode}\n{env}{line}\n{msg}\n{line}'.format(
            returncode=returncode, env=envstr, line='-' * 60, msg=message
        )
        super().__init__(msg)


class SubprocessTestCase(unittest.TestCase):
    def assertExistence(self, path, exists):
        if os.path.exists(path) != exists:
            msg = '{!r} does not exist' if exists else '{!r} exists'
            raise unittest.TestCase.failureException(
                msg.format(os.path.normpath(path))
            )

    def assertExists(self, path):
        self.assertExistence(path, True)

    def assertNotExists(self, path):
        self.assertExistence(path, False)

    def assertPopen(self, command, *, env=None, extra_env=None, returncode=0):
        final_env = env if env is not None else os.environ
        if extra_env:
            final_env = final_env.copy()
            final_env.update(extra_env)

        proc = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=final_env, universal_newlines=True
        )
        if not (returncode == 'any' or
                (returncode == 'fail' and proc.returncode != 0) or
                proc.returncode in listify(returncode)):
            raise SubprocessError(proc.returncode, extra_env or env,
                                  proc.stdout)
        return proc.stdout

    def assertOutput(self, command, output, *args, **kwargs):
        self.assertEqual(self.assertPopen(command, *args, **kwargs), output)


class IntegrationTest(SubprocessTestCase):
    deploy = False

    def setUp(self):
        self.stage = stage_dir(self.name)
        self.pkgbuilddir = os.path.join(self.stage, 'mopack', 'build')
        if self.deploy:
            self.prefix = stage_dir(self.name + '-install', chdir=False)

    def assertUsage(self, name, usage='', extra_args=[], *, format='json',
                    submodules=[], extra_env=usage_env, returncode=0):
        loader = {
            'json': json.loads,
            'yaml': yaml.safe_load,
        }

        output = self.assertPopen((
            ['mopack', 'usage', name] +
            (['--json'] if format == 'json' else []) +
            ['-s' + i for i in submodules] +
            extra_args
        ), extra_env=extra_env, returncode=returncode)
        if returncode == 0:
            self.assertEqual(loader[format](output), usage)
        return output

    def assertPkgConfigUsage(self, name, *, path=['pkgconfig'], pcfiles=None,
                             extra_args=[], submodules=[]):
        path = [(i if os.path.isabs(i) else
                 os.path.join(self.pkgbuilddir, name, i)) for i in path]
        if pcfiles is None:
            pcfiles = [name]

        self.assertUsage(name, {
            'name': dependency_string(name, submodules), 'type': 'pkg_config',
            'path': path, 'pcfiles': pcfiles, 'extra_args': extra_args,
        }, submodules=submodules)

    def assertPathUsage(self, name, *, type='path', auto_link=False,
                        include_path=[], library_path=[], headers=[],
                        libraries=None, compile_flags=[], link_flags=[],
                        submodules=[], version=''):
        if libraries is None:
            libraries = [name]
        pkgconfdir = os.path.join(self.stage, 'mopack', 'pkgconfig')
        self.assertUsage(name, {
            'name': dependency_string(name, submodules), 'type': type,
            'generated': True, 'auto_link': auto_link, 'path': [pkgconfdir],
            'pcfiles': [name],
        }, submodules=submodules)

        self.assertCountEqual(
            call_pkg_config(name, ['--cflags'], path=pkgconfdir),
            ['-I' + i for i in include_path] + compile_flags
        )
        self.assertCountEqual(
            call_pkg_config(name, ['--libs'], path=pkgconfdir),
            (['-L' + i for i in library_path] + link_flags +
             ['-l' + i for i in libraries])
        )
        self.assertEqual(
            call_pkg_config(name, ['--modversion'], path=pkgconfdir,
                            split=False),
            version
        )
