"""Use conda-pack's relocation logic without opening unchanged DLLs for writing.

Windows locks loaded extension modules (e.g. _bz2.pyd). conda-pack 0.9.2
opens every prefix record as rb+, including DLLs whose bytes do not change.
Patch only its generated unpack script, retaining upstream replacement,
PowerShell normalization, macOS signing, and license text unchanged.
"""
from pathlib import Path


BEFORE = """    with open(path, 'rb+') as fh:
        original_data = fh.read()
        fh.seek(0)

        data = replace_prefix(original_data, mode, placeholder, new_prefix)

        # If the before and after content is the same, skip writing
        if data != original_data:
            fh.write(data)
            fh.truncate()
            file_changed = True
"""
AFTER = """    # GAIA: loaded Windows DLLs can be read but cannot be opened for writing.
    with open(path, 'rb') as fh:
        original_data = fh.read()
    data = replace_prefix(original_data, mode, placeholder, new_prefix)
    if data != original_data:
        with open(path, 'rb+') as fh:
            fh.write(data)
            fh.truncate()
        file_changed = True
"""


def relocation_source(source):
    if source.count(BEFORE) != 1:
        raise RuntimeError('conda-pack relocation code changed; review the read-first patch before packaging')
    return source.replace(BEFORE, AFTER, 1)


class ReadFirstTemplate(str):
    def format(self, **kwargs):
        kwargs['prefixes_py'] = relocation_source(kwargs['prefixes_py'])
        return super().format(**kwargs)


def main():
    from conda_pack import cli, core
    # Fail before spending time packing if the pinned upstream version changes.
    relocation_source((Path(core.__file__).parent / 'prefixes.py').read_text())
    core._conda_unpack_template = ReadFirstTemplate(core._conda_unpack_template)
    cli.main()


if __name__ == '__main__':
    main()
