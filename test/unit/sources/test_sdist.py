import os
from unittest import mock, TestCase

from .. import mock_open_log
from ... import *

from mopack.builders.bfg9000 import Bfg9000Builder
from mopack.config import Config
from mopack.sources import Package
from mopack.sources.apt import AptPackage
from mopack.sources.sdist import DirectoryPackage, TarballPackage

mock_bfgclean = 'mopack.builders.bfg9000.Bfg9000Builder.clean'


def mock_open_after_first(*args, **kwargs):
    _open = open
    mock_open = mock.mock_open(*args, **kwargs)

    def non_mock(*args, **kwargs):
        mock_open.side_effect = None
        return _open(*args, **kwargs)

    mock_open.side_effect = non_mock
    return mock_open


class SDistTestCase(TestCase):
    config_file = '/path/to/mopack.yml'
    pkgdir = '/path/to/builddir/mopack'
    deploy_paths = {'prefix': '/usr/local'}

    def pkgconfdir(self, name):
        return os.path.join(self.pkgdir, 'build', name, 'pkgconfig')


class TestDirectory(SDistTestCase):
    srcpath = os.path.join(test_data_dir, 'bfg_project')

    def test_resolve(self):
        pkg = DirectoryPackage('foo', path=self.srcpath, build='bfg9000',
                               config_file=self.config_file)
        self.assertEqual(pkg.path, self.srcpath)
        self.assertEqual(pkg.builder, Bfg9000Builder('foo'))

        pkg.fetch(self.pkgdir, None)

        with mock_open_log() as mopen, \
             mock.patch('mopack.builders.bfg9000.pushd'), \
             mock.patch('subprocess.check_call'):  # noqa
            info = pkg.resolve(self.pkgdir, self.deploy_paths)
            self.assertEqual(info, {
                'config': {'name': 'foo',
                           'config_file': self.config_file,
                           'source': 'directory',
                           'path': self.srcpath,
                           'builder': {
                               'type': 'bfg9000',
                               'name': 'foo',
                               'extra_args': [],
                               'usage': {
                                   'type': 'pkg-config',
                                   'path': 'pkgconfig',
                               },
                           }},
                'usage': {'type': 'pkg-config', 'path': self.pkgconfdir('foo')}
            })

            mopen.assert_called_with(os.path.join(self.pkgdir, 'foo.log'), 'w')

    def test_build(self):
        build = {'type': 'bfg9000', 'extra_args': '--extra'}
        pkg = DirectoryPackage('foo', path=self.srcpath, build=build,
                               usage='pkg-config',
                               config_file=self.config_file)
        self.assertEqual(pkg.path, self.srcpath)
        self.assertEqual(pkg.builder, Bfg9000Builder(
            'foo', extra_args='--extra'
        ))

    def test_infer_build(self):
        pkg = DirectoryPackage('foo', path=self.srcpath,
                               config_file=self.config_file)
        self.assertEqual(pkg.builder, None)

        with mock.patch('os.path.exists', return_value=True):
            config = pkg.fetch(self.pkgdir, Config([]))
            self.assertEqual(config.build, 'bfg9000')
            self.assertEqual(pkg.builder, Bfg9000Builder('foo'))

        usage = {'type': 'system'}
        pkg = DirectoryPackage('foo', path=self.srcpath, usage=usage,
                               config_file=self.config_file)

        with mock.patch('os.path.exists', return_value=True):
            config = pkg.fetch(self.pkgdir, Config([]))
            self.assertEqual(config.build, 'bfg9000')
            self.assertEqual(pkg.builder, Bfg9000Builder('foo', usage=usage))

    def test_usage(self):
        pkg = DirectoryPackage('foo', path=self.srcpath, build='bfg9000',
                               usage='pkg-config',
                               config_file=self.config_file)
        self.assertEqual(pkg.path, self.srcpath)
        self.assertEqual(pkg.builder, Bfg9000Builder(
            'foo', usage='pkg-config'
        ))

        usage = {'type': 'pkg-config', 'path': 'pkgconf'}
        pkg = DirectoryPackage('foo', path=self.srcpath, build='bfg9000',
                               usage=usage, config_file=self.config_file)
        self.assertEqual(pkg.path, self.srcpath)
        self.assertEqual(pkg.builder, Bfg9000Builder('foo', usage=usage))

    def test_deploy(self):
        pkg = DirectoryPackage('foo', path=self.srcpath, build='bfg9000',
                               config_file=self.config_file)

        with mock_open_log() as mopen, \
             mock.patch('mopack.builders.bfg9000.pushd'), \
             mock.patch('subprocess.check_call'):  # noqa
            pkg.deploy(self.pkgdir)
            mopen.assert_called_with(
                os.path.join(self.pkgdir, 'foo-deploy.log'), 'w'
            )

    def test_clean_pre(self):
        oldpkg = DirectoryPackage('foo', build='bfg9000', path=self.srcpath,
                                  config_file=self.config_file)
        newpkg = AptPackage('foo', config_file=self.config_file)

        # System -> Apt
        self.assertEqual(oldpkg.clean_pre(self.pkgdir, newpkg), False)

        # Apt -> nothing
        self.assertEqual(oldpkg.clean_pre(self.pkgdir, None), False)

    def test_clean_post(self):
        otherpath = os.path.join(test_data_dir, 'other_project')

        oldpkg = DirectoryPackage('foo', build='bfg9000', path=self.srcpath,
                                  config_file=self.config_file)
        newpkg1 = DirectoryPackage('foo', build='bfg9000', path=otherpath,
                                   config_file=self.config_file)
        newpkg2 = AptPackage('foo', config_file=self.config_file)

        # Directory -> Directory (same)
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean:  # noqa
            self.assertEqual(oldpkg.clean_post(self.pkgdir, oldpkg), False)
            mlog.assert_not_called()
            mclean.assert_not_called()

        # Directory -> Directory (different)
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean:  # noqa
            self.assertEqual(oldpkg.clean_post(self.pkgdir, newpkg1), True)
            mlog.assert_called_once()
            mclean.assert_called_once_with(self.pkgdir)

        # Directory -> Apt
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean:  # noqa
            self.assertEqual(oldpkg.clean_post(self.pkgdir, newpkg2), True)
            mlog.assert_called_once()
            mclean.assert_called_once_with(self.pkgdir)

        # Directory -> nothing
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean:  # noqa
            self.assertEqual(oldpkg.clean_post(self.pkgdir, None), True)
            mlog.assert_called_once()
            mclean.assert_called_once_with(self.pkgdir)

    def test_clean_all(self):
        otherpath = os.path.join(test_data_dir, 'other_project')

        oldpkg = DirectoryPackage('foo', build='bfg9000', path=self.srcpath,
                                  config_file=self.config_file)
        newpkg1 = DirectoryPackage('foo', build='bfg9000', path=otherpath,
                                   config_file=self.config_file)
        newpkg2 = AptPackage('foo', config_file=self.config_file)

        # Directory -> Directory (same)
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean:  # noqa
            self.assertEqual(oldpkg.clean_all(self.pkgdir, oldpkg),
                             (False, False))
            mlog.assert_not_called()
            mclean.assert_not_called()

        # Directory -> Directory (different)
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean:  # noqa
            self.assertEqual(oldpkg.clean_all(self.pkgdir, newpkg1),
                             (False, True))
            mlog.assert_called_once()
            mclean.assert_called_once_with(self.pkgdir)

        # Directory -> Apt
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean:  # noqa
            self.assertEqual(oldpkg.clean_all(self.pkgdir, newpkg2),
                             (False, True))
            mlog.assert_called_once()
            mclean.assert_called_once_with(self.pkgdir)

        # Directory -> nothing
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean:  # noqa
            self.assertEqual(oldpkg.clean_all(self.pkgdir, None),
                             (False, True))
            mlog.assert_called_once()
            mclean.assert_called_once_with(self.pkgdir)

    def test_equality(self):
        otherpath = os.path.join(test_data_dir, 'other_project')
        pkg = DirectoryPackage('foo', build='bfg9000', path=self.srcpath,
                               config_file=self.config_file)

        self.assertEqual(pkg, DirectoryPackage(
            'foo', build='bfg9000', path=self.srcpath,
            config_file=self.config_file
        ))
        self.assertEqual(pkg, DirectoryPackage(
            'foo', build='bfg9000', path=self.srcpath,
            config_file='/path/to/mopack2.yml'
        ))

        self.assertNotEqual(pkg, DirectoryPackage(
            'bar', build='bfg9000', path=self.srcpath,
            config_file=self.config_file
        ))
        self.assertNotEqual(pkg, DirectoryPackage(
            'foo', build='bfg9000', path=otherpath,
            config_file=self.config_file
        ))

    def test_rehydrate(self):
        pkg = DirectoryPackage('foo', build='bfg9000', path=self.srcpath,
                               config_file=self.config_file)
        data = pkg.dehydrate()
        self.assertNotIn('pending_usage', data)
        self.assertEqual(pkg, Package.rehydrate(data))

        pkg = DirectoryPackage('foo', path=self.srcpath,
                               config_file=self.config_file)
        with self.assertRaises(TypeError):
            data = pkg.dehydrate()


class TestTarball(SDistTestCase):
    srcurl = 'http://example.invalid/bfg_project.tar.gz'
    srcpath = os.path.join(test_data_dir, 'bfg_project.tar.gz')

    @staticmethod
    def _mock_urlopen(url):
        return open(os.path.join(test_data_dir, 'bfg_project.tar.gz'), 'rb')

    def _check_resolve(self, pkg, url=None, path=None):
        with mock_open_log() as mopen, \
             mock.patch('mopack.builders.bfg9000.pushd'), \
             mock.patch('subprocess.check_call'):  # noqa
            info = pkg.resolve(self.pkgdir, self.deploy_paths)
            self.assertEqual(info, {
                'config': {'name': 'foo',
                           'config_file': self.config_file,
                           'source': 'tarball',
                           'path': path,
                           'url': url,
                           'files': None,
                           'srcdir': None,
                           'guessed_srcdir': 'bfg_project',
                           'builder': {
                               'type': 'bfg9000',
                               'name': 'foo',
                               'extra_args': [],
                               'usage': {
                                   'type': 'pkg-config',
                                   'path': 'pkgconfig',
                               },
                           }},
                'usage': {'type': 'pkg-config', 'path': self.pkgconfdir('foo')}
            })

            mopen.assert_called_with(os.path.join(self.pkgdir, 'foo.log'), 'w')

    def test_url(self):
        pkg = TarballPackage('foo', build='bfg9000', url=self.srcurl,
                             config_file=self.config_file)
        self.assertEqual(pkg.url, self.srcurl)
        self.assertEqual(pkg.path, None)

        srcdir = os.path.join(self.pkgdir, 'src', 'foo')
        with mock.patch('mopack.sources.sdist.urlopen', self._mock_urlopen), \
             mock.patch('tarfile.TarFile.extractall') as mtar:  # noqa
            pkg.fetch(self.pkgdir, None)
            mtar.assert_called_once_with(srcdir)

        self._check_resolve(pkg, url=self.srcurl)

    def test_path(self):
        pkg = TarballPackage('foo', build='bfg9000', path=self.srcpath,
                             config_file=self.config_file)
        self.assertEqual(pkg.url, None)
        self.assertEqual(pkg.path, self.srcpath)

        srcdir = os.path.join(self.pkgdir, 'src', 'foo')
        with mock.patch('tarfile.TarFile.extractall') as mtar:
            pkg.fetch(self.pkgdir, None)
            mtar.assert_called_once_with(srcdir)

        self._check_resolve(pkg, path=self.srcpath)

    def test_missing_url_path(self):
        with self.assertRaises(TypeError):
            TarballPackage('foo', build='bfg9000',
                           config_file=self.config_file)

    def test_build(self):
        build = {'type': 'bfg9000', 'extra_args': '--extra'}
        pkg = TarballPackage('foo', path=self.srcpath, build=build,
                             usage='pkg-config', config_file=self.config_file)
        self.assertEqual(pkg.path, self.srcpath)
        self.assertEqual(pkg.builder, Bfg9000Builder(
            'foo', extra_args='--extra'
        ))

    def test_infer_build(self):
        pkg = TarballPackage('foo', path=self.srcpath,
                             config_file=self.config_file)
        self.assertEqual(pkg.builder, None)

        with mock.patch('os.path.exists', return_value=True), \
             mock.patch('builtins.open', mock_open_after_first(
                 read_data='self:\n  build: bfg9000'
             )), \
             mock.patch('tarfile.TarFile.extractall') as mtar:  # noqa
            config = pkg.fetch(self.pkgdir, Config([]))
            self.assertEqual(config.build, 'bfg9000')
            self.assertEqual(pkg.builder, Bfg9000Builder('foo'))

        usage = {'type': 'system'}
        pkg = TarballPackage('foo', path=self.srcpath, usage=usage,
                             config_file=self.config_file)

        with mock.patch('os.path.exists', return_value=True), \
             mock.patch('builtins.open', mock_open_after_first(
                 read_data='self:\n  build: bfg9000'
             )), \
             mock.patch('tarfile.TarFile.extractall') as mtar:  # noqa
            config = pkg.fetch(self.pkgdir, Config([]))
            self.assertEqual(config.build, 'bfg9000')
            self.assertEqual(pkg.builder, Bfg9000Builder('foo', usage=usage))

    def test_usage(self):
        pkg = TarballPackage('foo', path=self.srcpath, build='bfg9000',
                             usage='pkg-config', config_file=self.config_file)
        self.assertEqual(pkg.path, self.srcpath)
        self.assertEqual(pkg.builder, Bfg9000Builder(
            'foo', usage='pkg-config'
        ))

        usage = {'type': 'pkg-config', 'path': 'pkgconf'}
        pkg = TarballPackage('foo', path=self.srcpath, build='bfg9000',
                             usage=usage, config_file=self.config_file)
        self.assertEqual(pkg.path, self.srcpath)
        self.assertEqual(pkg.builder, Bfg9000Builder('foo', usage=usage))

    def test_deploy(self):
        pkg = TarballPackage('foo', build='bfg9000', url='http://example.com',
                             config_file=self.config_file)

        with mock_open_log() as mopen, \
             mock.patch('mopack.builders.bfg9000.pushd'), \
             mock.patch('subprocess.check_call'):  # noqa
            pkg.deploy(self.pkgdir)
            mopen.assert_called_with(
                os.path.join(self.pkgdir, 'foo-deploy.log'), 'w'
            )

    def test_clean_pre(self):
        path1 = os.path.join(test_data_dir, 'bfg_project.tar.gz')
        path2 = os.path.join(test_data_dir, 'other_project.tar.gz')

        oldpkg = TarballPackage('foo', build='bfg9000', path=path1,
                                srcdir='bfg_project',
                                config_file=self.config_file)
        newpkg1 = TarballPackage('foo', build='bfg9000', path=path2,
                                 config_file=self.config_file)
        newpkg2 = AptPackage('foo', config_file=self.config_file)

        srcdir = os.path.join(self.pkgdir, 'src', 'foo')

        # Tarball -> Tarball (same)
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch('shutil.rmtree') as mrmtree:  # noqa
            self.assertEqual(oldpkg.clean_pre(self.pkgdir, oldpkg), False)
            mlog.assert_not_called()
            mrmtree.assert_not_called()

        # Tarball -> Tarball (different)
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch('shutil.rmtree') as mrmtree:  # noqa
            self.assertEqual(oldpkg.clean_pre(self.pkgdir, newpkg1), True)
            mlog.assert_called_once()
            mrmtree.assert_called_once_with(srcdir, ignore_errors=True)

        # Tarball -> Apt
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch('shutil.rmtree') as mrmtree:  # noqa
            self.assertEqual(oldpkg.clean_pre(self.pkgdir, newpkg2), True)
            mlog.assert_called_once()
            mrmtree.assert_called_once_with(srcdir, ignore_errors=True)

        # Tarball -> nothing
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch('shutil.rmtree') as mrmtree:  # noqa
            self.assertEqual(oldpkg.clean_pre(self.pkgdir, None), True)
            mlog.assert_called_once()
            mrmtree.assert_called_once_with(srcdir, ignore_errors=True)

    def test_clean_post(self):
        path1 = os.path.join(test_data_dir, 'bfg_project.tar.gz')
        path2 = os.path.join(test_data_dir, 'other_project.tar.gz')

        oldpkg = TarballPackage('foo', build='bfg9000', path=path1,
                                srcdir='bfg_project',
                                config_file=self.config_file)
        newpkg1 = TarballPackage('foo', build='bfg9000', path=path2,
                                 config_file=self.config_file)
        newpkg2 = AptPackage('foo', config_file=self.config_file)

        # Tarball -> Tarball (same)
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean:  # noqa
            self.assertEqual(oldpkg.clean_post(self.pkgdir, oldpkg), False)
            mlog.assert_not_called()
            mclean.assert_not_called()

        # Tarball -> Tarball (different)
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean:  # noqa
            self.assertEqual(oldpkg.clean_post(self.pkgdir, newpkg1), True)
            mlog.assert_called_once()
            mclean.assert_called_once_with(self.pkgdir)

        # Tarball -> Apt
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean:  # noqa
            self.assertEqual(oldpkg.clean_post(self.pkgdir, newpkg2), True)
            mlog.assert_called_once()
            mclean.assert_called_once_with(self.pkgdir)

        # Tarball -> nothing
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean:  # noqa
            self.assertEqual(oldpkg.clean_post(self.pkgdir, None), True)
            mlog.assert_called_once()
            mclean.assert_called_once_with(self.pkgdir)

    def test_clean_all(self):
        path1 = os.path.join(test_data_dir, 'bfg_project.tar.gz')
        path2 = os.path.join(test_data_dir, 'other_project.tar.gz')

        oldpkg = TarballPackage('foo', build='bfg9000', path=path1,
                                srcdir='bfg_project',
                                config_file=self.config_file)
        newpkg1 = TarballPackage('foo', build='bfg9000', path=path2,
                                 config_file=self.config_file)
        newpkg2 = AptPackage('foo', config_file=self.config_file)

        srcdir = os.path.join(self.pkgdir, 'src', 'foo')

        # Tarball -> Tarball (same)
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean, \
             mock.patch('shutil.rmtree') as mrmtree:  # noqa
            self.assertEqual(oldpkg.clean_all(self.pkgdir, oldpkg),
                             (False, False))
            mlog.assert_not_called()
            mclean.assert_not_called()
            mrmtree.assert_not_called()

        # Tarball -> Tarball (different)
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean, \
             mock.patch('shutil.rmtree') as mrmtree:  # noqa
            self.assertEqual(oldpkg.clean_all(self.pkgdir, newpkg1),
                             (True, True))
            self.assertEqual(mlog.call_count, 2)
            mclean.assert_called_once_with(self.pkgdir)
            mrmtree.assert_called_once_with(srcdir, ignore_errors=True)

        # Tarball -> Apt
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean, \
             mock.patch('shutil.rmtree') as mrmtree:  # noqa
            self.assertEqual(oldpkg.clean_all(self.pkgdir, newpkg2),
                             (True, True))
            self.assertEqual(mlog.call_count, 2)
            mclean.assert_called_once_with(self.pkgdir)
            mrmtree.assert_called_once_with(srcdir, ignore_errors=True)

        # Tarball -> nothing
        with mock.patch('mopack.log.info') as mlog, \
             mock.patch(mock_bfgclean) as mclean, \
             mock.patch('shutil.rmtree') as mrmtree:  # noqa
            self.assertEqual(oldpkg.clean_all(self.pkgdir, None),
                             (True, True))
            self.assertEqual(mlog.call_count, 2)
            mclean.assert_called_once_with(self.pkgdir)
            mrmtree.assert_called_once_with(srcdir, ignore_errors=True)

    def test_equality(self):
        otherpath = os.path.join(test_data_dir, 'other_project.tar.gz')
        pkg = TarballPackage('foo', build='bfg9000', path=self.srcpath,
                             config_file=self.config_file)

        self.assertEqual(pkg, TarballPackage(
            'foo', build='bfg9000', path=self.srcpath,
            config_file=self.config_file
        ))
        self.assertEqual(pkg, TarballPackage(
            'foo', build='bfg9000', path=self.srcpath,
            config_file='/path/to/mopack2.yml'
        ))

        self.assertNotEqual(pkg, TarballPackage(
            'bar', build='bfg9000', path=self.srcpath,
            config_file=self.config_file
        ))
        self.assertNotEqual(pkg, TarballPackage(
            'foo', build='bfg9000', url=self.srcurl,
            config_file=self.config_file
        ))
        self.assertNotEqual(pkg, TarballPackage(
            'foo', build='bfg9000', path=otherpath,
            config_file=self.config_file
        ))

    def test_rehydrate(self):
        pkg = TarballPackage('foo', build='bfg9000', path=self.srcpath,
                             config_file=self.config_file)
        data = pkg.dehydrate()
        self.assertEqual(pkg, Package.rehydrate(data))

        pkg = TarballPackage('foo', path=self.srcpath,
                             config_file=self.config_file)
        with self.assertRaises(TypeError):
            data = pkg.dehydrate()
