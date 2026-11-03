"""Validate DBF text and repair only provably truncated field-name tails on a copy."""
import codecs
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory


class EncodingNeedsInput(ValueError):
    def __init__(self,message):
        super().__init__(message)
        self.report={'passed':False,'errors':[message],'warnings':[],'unverified':[],
                     'needs_user_input':True,'scope':'shapefile_text'}


def sidecar(path, extension):
    return next((p for p in path.parent.iterdir() if p.is_file() and
                 p.name.casefold() == (path.stem + extension).casefold()), None)


def normalize_encoding(value):
    if not value or value == 'auto':
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError('文字编码必须是有效编码名称，例如 UTF-8、GBK 或 GB18030。')
    name = value.strip().strip('\"\'')
    name = {'65001': 'utf-8', '936': 'gbk', 'windows-936': 'gbk',
            '950': 'big5', '1252': 'cp1252'}.get(name.lower(), name)
    try:
        codec = codecs.lookup(name)
        if not codec._is_text_encoding:
            raise LookupError()
    except LookupError:
        raise ValueError('无法识别文字编码；请选择 UTF-8、GBK、GB18030 或其他实际编码。') from None
    return codec.name


def dbf_header(path):
    file = sidecar(path, '.dbf')
    if file is None:
        raise ValueError('Shapefile 缺少 .dbf 属性文件，请上传全部配套文件。')
    with file.open('rb') as stream:
        head = stream.read(32)
        if len(head) != 32:
            raise ValueError('DBF 文件头不完整，请检查配套文件。')
        size = int.from_bytes(head[8:10], 'little')
        record_size = int.from_bytes(head[10:12], 'little')
        records = int.from_bytes(head[4:8], 'little')
        if size < 33 or record_size < 1:
            raise ValueError('DBF 文件头长度无效。')
        header = head + stream.read(size - 32)
    if len(header) != size or size + record_size * records > file.stat().st_size:
        raise ValueError('DBF 文件被截断，记录长度与文件大小不一致；请重新导出数据。')
    fields = []
    offset = 1
    for start in range(32, size - 1, 32):
        descriptor = header[start:start + 32]
        if descriptor[:1] == b'\r':
            break
        if len(descriptor) != 32:
            raise ValueError('DBF 字段定义不完整。')
        fields.append({'index': len(fields) + 1, 'start': start,
                       'raw': descriptor[:11].split(b'\0', 1)[0].rstrip(b' '),
                       'kind': chr(descriptor[11]), 'size': descriptor[16], 'offset': offset})
        offset += descriptor[16]
    if offset > record_size:
        raise ValueError('DBF 字段宽度超出记录长度。')
    return file, header, record_size, records, fields


def inspect_shapefile(path, encoding=None):
    path = Path(path)
    override = normalize_encoding(encoding)
    cpg = sidecar(path, '.cpg')
    declared = None
    if cpg:
        with cpg.open('rb') as stream:
            raw = stream.read(1024)
        try:
            declared = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig').strip()
        except UnicodeError:
            declared = ''
    try:
        effective = override or normalize_encoding(declared)
    except ValueError:
        effective = override
    file, header, record_size, records, fields = dbf_header(path)
    if records > 100000:
        raise ValueError('本版单图层最多支持 100,000 条记录。')
    issues = []
    if effective:
        for field in fields:
            try:
                field['raw'].decode(effective)
            except UnicodeDecodeError as error:
                truncated = len(field['raw']) in (10, 11) and error.end == len(field['raw']) and error.reason in (
                    'unexpected end of data', 'incomplete multibyte sequence')
                issues.append({'index': field['index'], 'raw_hex': field['raw'].hex(),
                               'truncated': truncated,
                               'valid_prefix': field['raw'][:error.start].decode(effective)})
    non_ascii = any(any(byte >= 128 for byte in field['raw']) for field in fields)
    if not non_ascii and not effective and (declared is not None or header[29] == 0):
        with file.open('rb') as stream:
            stream.seek(len(header))
            for _ in range(records):
                record=stream.read(record_size)
                if record[:1] == b'*':continue
                if any(any(byte >= 128 for byte in record[field['offset']:field['offset']+field['size']])
                       for field in fields if field['kind']=='C'):
                    non_ascii=True;break
    needs_encoding=not effective and non_ascii and (declared is not None or header[29] == 0)
    return {'declared_encoding': declared, 'encoding': effective,'needs_encoding':needs_encoding,
            'encoding_source': 'user' if override else 'cpg' if effective else 'gdal',
            'field_name_issues': issues}


def validate_values(file, header, record_size, records, fields, encoding):
    if not encoding:
        return
    with file.open('rb') as stream:
        stream.seek(len(header))
        for row in range(records):
            record = stream.read(record_size)
            if record[:1] == b'*':
                continue
            for field in fields:
                if field['kind'] != 'C':
                    continue
                value = record[field['offset']:field['offset'] + field['size']].rstrip(b' \0')
                try:
                    value.decode(encoding)
                except UnicodeDecodeError:
                    raise EncodingNeedsInput(f'DBF 第 {row + 1} 条记录、第 {field["index"]} 个字段无法按 {encoding} 解码。'
                                     '请核对 .cpg，或在导入窗口指定实际文字编码；未丢弃或替换属性值。') from None


def read_shapefile(path, options=None, encoding=None, repair_truncated_fields=True):
    import geopandas as gpd
    path = Path(path)
    info = inspect_shapefile(path, encoding)
    if info['needs_encoding']:
        raise EncodingNeedsInput('DBF 含非 ASCII 文本，但缺少可识别的编码声明。请在“Shapefile 文字编码”中选择实际编码（UTF-8、GBK 或 GB18030），避免导入乱码。')
    issues = info['field_name_issues']
    if any(not issue['truncated'] for issue in issues):
        raise EncodingNeedsInput('DBF 字段名与文字编码声明不一致。请核对 .cpg，或指定实际文字编码，例如 GBK / GB18030；未修改源文件。')
    if issues and not repair_truncated_fields:
        raise ValueError('DBF 字段名的多字节字符被长度限制截断。可允许生成安全字段别名，或在 QGIS 中重命名字段后另存 GeoPackage。')
    file, header, record_size, records, fields = dbf_header(path)
    if records > 100000:
        raise ValueError('本版单图层最多支持 100,000 条记录。')
    validate_values(file, header, record_size, records, fields, info['encoding'])
    options = dict(options or {})
    if info['encoding']:
        options['encoding'] = info['encoding']
    repairs = []
    try:
        if not issues:
            return gpd.read_file(path, engine='pyogrio', **options), info, repairs
        # Names cannot be reconstructed from missing bytes. Keep the source intact
        # and use explicit, unique ASCII aliases; never guess the missing meaning.
        taken = {field['raw'].decode(info['encoding']).casefold() for field in fields
                 if field['index'] not in {issue['index'] for issue in issues}}
        fixed = bytearray(header)
        for issue in issues:
            alias = f'field_{issue["index"]}'
            number = 1
            while alias.casefold() in taken:
                alias = f'f{issue["index"]}_{number}';number += 1
            taken.add(alias.casefold())
            field = fields[issue['index'] - 1]
            fixed[field['start']:field['start'] + 11] = alias.encode().ljust(11, b'\0')
            repairs.append({**issue, 'alias': alias})
        with TemporaryDirectory(prefix='gaia-shp-text-') as folder:
            copy = Path(folder) / (path.stem + '.shp')
            for source in path.parent.iterdir():
                if source.is_file() and source.stem.casefold() == path.stem.casefold() and source.suffix.lower() in {
                    '.shp','.shx','.dbf','.prj','.cpg','.qix','.sbn','.sbx','.qpj','.idm','.ind'}:
                    shutil.copyfile(source, Path(folder) / (path.stem + source.suffix.lower()))
            target = copy.with_suffix('.dbf')
            with target.open('r+b') as stream:
                stream.write(fixed)
            # A Shapefile has one layer. Explicit names from the original file
            # remain valid because the temporary copy keeps the same basename.
            return gpd.read_file(copy, engine='pyogrio', **options), info, repairs
    except UnicodeDecodeError:
        raise EncodingNeedsInput('Shapefile 的字段名或属性文本无法解码。请指定实际文字编码，或在 QGIS 中另存为 GeoPackage；未修改源文件。') from None
