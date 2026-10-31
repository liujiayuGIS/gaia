"""Exercise the real generated relocation code, including locked-DLL behavior."""
import builtins
import importlib.util
from pathlib import Path

import pytest
from conda_pack import core, prefixes

spec = importlib.util.spec_from_file_location('pack_runtime', Path(__file__).parents[1] / 'pack_runtime.py')
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)


def generated_namespace():
    template = pack.ReadFirstTemplate(core._conda_unpack_template)
    script = template.format(shebang='', prefixes_py=Path(prefixes.__file__).read_text(),
                             prefix_records='', version='test')
    # Compile exactly what conda-pack puts in the archive; don't run the CLI loop.
    namespace = {'__name__': 'relocation_test'}
    # Progress module is bundled beside the generated script, but not installed.
    script = script.replace('from conda_unpack_progress import progressbar', '')
    exec(compile(script, 'conda-unpack-script.py', 'exec'), namespace)
    namespace['on_win'] = True
    return namespace


def test_unchanged_loaded_dll_never_opened_for_write(tmp_path):
    namespace = generated_namespace()
    dll = tmp_path / '_bz2.pyd'
    data = b'MZ\0DLL fixture with no pyzzer entrypoint'
    dll.write_bytes(data)
    modes = []

    def locked_open(path, mode):
        modes.append(mode)
        if mode != 'rb':
            raise PermissionError('Windows loaded DLL lock')
        return builtins.open(path, mode)

    namespace['open'] = locked_open
    namespace['update_prefix'](str(dll), 'C:/new', 'C:/old', 'binary')
    assert modes == ['rb']
    assert dll.read_bytes() == data


def test_required_relocation_still_writes_and_truncates(tmp_path):
    namespace = generated_namespace()
    config = tmp_path / 'settings.txt'
    config.write_bytes(b'prefix=C:/long/original/path\n')
    namespace['update_prefix'](str(config), 'C:\\new', 'C:/long/original/path')
    assert config.read_bytes() == b'prefix=C:/new\n'


def test_needed_write_errors_are_not_suppressed(tmp_path):
    namespace = generated_namespace()
    config = tmp_path / 'settings.txt'
    config.write_bytes(b'C:/old')
    def locked_open(path, mode):
        if mode != 'rb':
            raise PermissionError('write denied')
        return builtins.open(path, mode)
    namespace['open'] = locked_open
    with pytest.raises(PermissionError, match='write denied'):
        namespace['update_prefix'](str(config), 'C:/new', 'C:/old')


def test_upstream_drift_fails_closed():
    with pytest.raises(RuntimeError, match='review'):
        pack.relocation_source('changed upstream implementation')
