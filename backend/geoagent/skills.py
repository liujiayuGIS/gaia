"""User-installable SKILL.md packages: procedural knowledge without extra privileges."""
import hashlib
import io
import json
from pathlib import Path
import uuid
import zipfile
import yaml

ROOT=Path(__file__).resolve().parents[2]


class SkillManager:
    def __init__(self,store):self.store=store

    def parse(self,path,source):
        text=path.read_text(encoding='utf-8-sig')
        if len(text)>60000:raise ValueError('SKILL.md 超过60,000字符。')
        if not text.startswith('---\n'):raise ValueError('SKILL.md 需要 YAML 元数据。')
        parts=text.split('---',2)
        if len(parts)!=3:raise ValueError('SKILL.md 元数据分隔符缺失。')
        try:meta=yaml.safe_load(parts[1])
        except yaml.YAMLError:raise ValueError('Skill YAML 元数据无效。') from None
        if not isinstance(meta,dict) or not meta.get('name') or not meta.get('description'):
            raise ValueError('Skill 需要 name 和 description。')
        identifier=hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:24]
        return {'id':identifier,'name':str(meta['name'])[:100],'description':str(meta['description'])[:1200],
            'version':str(meta.get('version','1')),'required_plugins':meta.get('required_plugins',[]),
            'sha256':hashlib.sha256(text.encode()).hexdigest(),'source':source,'path':str(path),
            'body':parts[2].strip(),'metadata':meta}

    def list(self,query=''):
        result=[]
        for root,source in [(ROOT/'skills','builtin'),(self.store.root/'skills','user')]:
            if not root.exists():continue
            for path in root.glob('*/SKILL.md'):
                skill=self.parse(path,source)
                if not query or query.lower() in (skill['name']+skill['description']).lower():
                    result.append({k:v for k,v in skill.items() if k not in ('body','metadata','path')})
        return result

    def read(self,skill_id):
        for root,source in [(ROOT/'skills','builtin'),(self.store.root/'skills','user')]:
            if not root.exists():continue
            for path in root.glob('*/SKILL.md'):
                skill=self.parse(path,source)
                if skill['id']==skill_id:return skill
        raise ValueError('Skill 不存在，请先检索技能。')

    def resource(self,skill_id,relative):
        skill=self.read(skill_id);root=Path(skill['path']).parent.resolve()
        path=(root/relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():raise ValueError('资源必须位于 Skill 包内。')
        if path.stat().st_size>200000:raise ValueError('Skill 文本资源超过200KB。')
        return {'skill_id':skill_id,'resource':relative,'text':path.read_text(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

    def install(self,filename,content):
        if len(content)>5*1024*1024:raise ValueError('Skill 包上限5MB。')
        folder=self.store.root/'skills'/uuid.uuid4().hex;folder.mkdir(parents=True)
        try:return self._install_package(filename,content,folder)
        except Exception as exc:
            import shutil
            shutil.rmtree(folder,ignore_errors=True)
            if isinstance(exc,zipfile.BadZipFile):raise ValueError('Skill ZIP 文件无效。') from None
            raise

    def _install_package(self,filename,content,folder):
        if filename.lower().endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if len(archive.infolist())>200 or sum(x.file_size for x in archive.infolist())>5*1024*1024:
                    raise ValueError('Skill 包解压后超过限制。')
                for item in archive.infolist():
                    target=(folder/item.filename).resolve()
                    if not target.is_relative_to(folder.resolve()) or (item.external_attr>>16)&0o170000==0o120000:
                        raise ValueError('Skill 包包含不安全路径。')
                archive.extractall(folder)
            files=list(folder.rglob('SKILL.md'))
            if len(files)!=1:raise ValueError('Skill 包需包含唯一 SKILL.md。')
            source=files[0].parent
            if source!=folder:
                import shutil
                temporary=folder.parent/(folder.name+'-flatten')
                shutil.copytree(source,temporary)
                shutil.rmtree(folder);temporary.rename(folder)
        else:(folder/'SKILL.md').write_bytes(content)
        result=self.parse(folder/'SKILL.md','user')
        return {k:v for k,v in result.items() if k not in ('body','metadata','path')}
