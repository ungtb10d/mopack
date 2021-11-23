from . import BinaryPackage
from .. import log
from ..types import FieldKeyError, Unset


class SystemPackage(BinaryPackage):
    source = 'system'
    _version = 1

    @staticmethod
    def upgrade(config, version):
        return config

    def __init__(self, name, *, version=Unset, auto_link=Unset,
                 include_path=Unset, library_path=Unset, headers=Unset,
                 libraries=Unset, compile_flags=Unset, link_flags=Unset,
                 submodule_map=Unset, usage=Unset, **kwargs):
        if usage is not Unset:
            raise FieldKeyError((
                "'system' package doesn't accept 'usage' attribute; " +
                'pass usage options directly'
            ), 'usage')

        super().__init__(name, usage={
            'type': 'system', 'auto_link': auto_link, 'version': version,
            'include_path': include_path, 'library_path': library_path,
            'headers': headers, 'libraries': libraries,
            'compile_flags': compile_flags, 'link_flags': link_flags,
            'submodule_map': submodule_map,
        }, _usage_field=None, **kwargs)

    def resolve(self, pkgdir):
        log.pkg_resolve(self.name, 'from {}'.format(self.source))
        self.resolved = True

    def deploy(self, pkgdir):
        pass


def fallback_system_package(name, options):
    pkg = SystemPackage(name, config_file=None, _options=options)
    pkg.resolved = True
    return pkg
