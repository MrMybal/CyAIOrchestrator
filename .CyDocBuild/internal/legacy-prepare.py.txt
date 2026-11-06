"""Prepare explicit, distributable CyDoc inputs without executing application source."""
from pathlib import Path
import hashlib,json,re,shutil,unicodedata
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'documentation';STAGE=BASE/'.generated'
SOURCE_FILES=['cyai/documentation.py','cyai/context.py','cyai/connectors.py','cyai/store.py','scripts/mcp_bridge.py','cyai/web/help.js','cyai/evaluation_kit/evalkit.py']
RESOURCE_FILES=['config.example.json','cyai/evaluation_kit/exercises.json','cyai/evaluation_kit/references.json','cyai/evaluation_kit/report-template.json']

def slug(text):return re.sub('[^a-z0-9]+','-',unicodedata.normalize('NFD',text).encode('ascii','ignore').decode().lower()).strip('-')
def front(id,title,description,section,order,body,translated=False):
    return f'---\nid: {id}\ntitle: {title.replace(chr(10)," ")}\ndescription: {description}\nsection: {section}\norder: {order}\nrevision: 1\n'+('sourceRevision: 1\n' if translated else '')+'---\n\n'+body.strip()+'\n'
def block(kind,value):return '```'+kind+'\n'+json.dumps(value,ensure_ascii=False)+'\n```\n'
def relative(path):return path.relative_to(ROOT).as_posix()
def headings(body):
    seen={};inside=False;result=[]
    for line in body.splitlines():
        if re.match(r'^\s*(`{3,}|~{3,})',line):inside=not inside
        match=re.match(r'^(#{1,6}) (.+)$',line) if not inside else None
        if match and not re.search(r'\{#[\w-]+\}\s*$',line):
            key=slug(match[2]) or 'section';seen[key]=seen.get(key,0)+1
            line+=' {#'+key+('-'+str(seen[key]) if seen[key]>1 else '')+'}'
        result.append(line)
    return '\n'.join(result)

def prepare():
    STAGE.mkdir(parents=True,exist_ok=True)
    for folder in ('manual','sources','export'):
        target=(STAGE/folder).resolve();assert target.parent==STAGE.resolve()
        if target.exists():shutil.rmtree(target)
        target.mkdir()
    for lang in ('en','fr'):shutil.copytree(BASE/'manual'/lang,STAGE/'manual'/lang,dirs_exist_ok=True)
    documents=[ROOT/'README.md',ROOT/'VALIDATION.md']+sorted((ROOT/'docs').glob('*.md'))+sorted((ROOT/'cyai/evaluation_kit').glob('*.md'))
    ids={relative(p):'reference-'+slug(relative(p).removesuffix('.md')) for p in documents}
    resources={name:'resource-'+slug(name) for name in RESOURCE_FILES}
    inventory=[];unresolved=[]
    def rewrite(body,source):
        def link(match):
            image,label,href=match.groups()
            if re.match(r'^(https?:|mailto:|doc:|#|assets/)',href):return match[0]
            name,_,anchor=href.partition('#')
            target=(source.parent/name).resolve()
            if not target.exists():target=(ROOT/name).resolve()
            if not target.is_relative_to(ROOT):unresolved.append({'source':relative(source),'target':href});return label+' (`'+href+'`)'
            key=relative(target)
            if key in ids:return '['+label+'](doc:'+ids[key]+('#'+anchor if anchor else '')+')'
            if key in resources:return '['+label+'](doc:'+resources[key]+('#'+anchor if anchor else '')+')'
            if image and target.is_file() and target.suffix.lower() in ('.png','.jpg','.jpeg','.svg','.webp'):
                file='reference-'+slug(key.rsplit('.',1)[0])+target.suffix.lower()
                shutil.copyfile(target,BASE/'assets/images'/file)
                return '!['+label+'](assets/images/'+file+')'
            if key in SOURCE_FILES:return '['+label+'](doc:source-generated-sources-'+slug(key)+('#'+anchor if anchor else '')+')'
            if name:
                unresolved.append({'source':relative(source),'target':href,'resolution':'Preserved as a literal repository path'})
                return label+' (`'+href+'`)'
            return match[0]
        # Change document links, not code examples containing Markdown.
        parts=re.split(r'(^```[^\n]*\n[\s\S]*?^```\s*$)',body,flags=re.M)
        return ''.join(part if part.startswith('```') else re.sub(r'(!?)\[([^\]]*)\]\(([^)]+)\)',link,part) for part in parts)
    current_release='docs/release-'+json.loads((BASE/'cydoc.config.json').read_text('utf-8'))['version']+'.md'
    for index,path in enumerate(documents):
        name=relative(path);original=path.read_text('utf-8')
        historical=(name in ('docs/architecture.md','VALIDATION.md') or bool(re.search(r'(?:0\.2\.|releases|team-board|audit|cyai3|ollama-rtx)',name))) and name != current_release
        source_language='en' if name in ('README.md','docs/plugins.md','docs/localization.md','docs/user-guide.md') or '/release-' in name else 'fr'
        title=re.search(r'^# (.+)$',original,re.M);title=title[1] if title else path.stem
        body=original
        if name=='README.md':
            body=re.sub(r'<p align="center">[\s\S]*?</p>','![CyAI Orchestrator](assets/images/logo.png)',body,count=1)
            body=body.replace('<details>','').replace('</details>','')
            body=re.sub(r'<summary>(.*?)</summary>',r'### \1',body)
        body=headings(rewrite(body,path))
        for lang in ('en','fr'):
            if historical:
                description=('Historical engineering record; not a current feature guarantee.' if lang=='en' else 'Note technique historique, pas une garantie des fonctionnalités actuelles.')
                notice=('This document is preserved for provenance. Version-specific results, paths and proposed features describe the original context. Use the current guides for normal operation.' if lang=='en' else 'Document conservé pour sa provenance. Résultats, chemins et fonctions proposées décrivent leur contexte initial. Consultez les guides actuels pour l’utilisation courante.')
                section='Historical notes' if lang=='en' else 'Notes historiques'
            else:
                description='Repository technical reference.' if lang=='en' else 'Référence technique du dépôt.'
                notice='Technical source preserved from the repository; use the user guide for the current interface.' if lang=='en' else 'Référence conservée depuis le dépôt ; le guide utilisateur décrit l’interface actuelle.'
                section='Developer references' if lang=='en' else 'Références développeur'
            if source_language!=lang:notice+=(' The original text below is in French; its English translation is pending.' if lang=='en' else ' Le texte original ci-dessous est en anglais ; sa traduction française reste à compléter.')
            (STAGE/'manual'/lang/(ids[name]+'.md')).write_text(front(ids[name],title,description,section,100+index,block('callout',{'type':'warning' if historical else 'info','title':'Source: '+name,'body':notice})+'\n'+body),'utf-8')
        inventory.append({'source':name,'id':ids[name],'sha256':hashlib.sha256(original.encode()).hexdigest(),'status':'historical' if historical else 'reference','originalLanguage':source_language,'translation':'original preserved; other-language prose needs review'})
    for name,id in resources.items():
        path=ROOT/name;source=path.read_text('utf-8')
        for lang in ('en','fr'):
            warning=('Evaluator references must not be sent to a test candidate.' if lang=='en' else 'Les corrigés de l’évaluateur ne doivent pas être transmis aux candidats.') if 'references.json' in name else ('Preserved repository resource, shown verbatim.' if lang=='en' else 'Ressource du dépôt conservée à l’identique.')
            body=warning+'\n\n```json\n'+source+'\n```'
            (STAGE/'manual'/lang/(id+'.md')).write_text(front(id,path.name,warning,'Evaluation resources' if lang=='en' else 'Ressources d’évaluation',180,body,translated=lang=='fr'),'utf-8')
        inventory.append({'source':name,'id':id,'sha256':hashlib.sha256(source.encode()).hexdigest(),'status':'resource'})
    for name in SOURCE_FILES:
        source=(ROOT/name).resolve();assert source.is_relative_to(ROOT) and not (ROOT/name).is_symlink()
        target=STAGE/'sources'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    for lang in ('en','fr'):
        title='Migration inventory' if lang=='en' else 'Inventaire de migration'
        body=('The 27 English/French guides retain their page IDs and explicit legacy anchors. All technical notes and evaluation resources listed below are preserved. Historical records may describe obsolete behaviour. Untranslated source-language references are identified, not presented as completed translations. Source indexing is lexical, not a semantic compiler.\n\n' if lang=='en' else 'Les 27 guides anglais/français conservent leurs identifiants et ancres. Toutes les notes et ressources ci-dessous sont préservées. Les archives peuvent décrire des comportements obsolètes. Les références non traduites sont signalées, pas présentées comme des traductions terminées. L’index du code est lexical, pas un compilateur sémantique.\n\n')
        body+='| Source | Page | Status |\n| --- | --- | --- |\n'+'\n'.join('| `'+x['source']+'` | ['+x['id']+'](doc:'+x['id']+') | '+x['status']+' |' for x in inventory)
        body+='\n\n## '+('References needing translation review' if lang=='en' else 'Références à traduire ou relire')+' {#translations}\n\n'+('The generated translation report marks preserved source-language references and extracted annotations as untracked. Authored bilingual guides use revision/sourceRevision. API docstrings are source text, not automatic translations.' if lang=='en' else 'Le rapport signale les références en langue d’origine et les annotations extraites comme non suivies. Les guides rédigés utilisent revision/sourceRevision. Les docstrings sont du texte source, pas des traductions automatiques.')
        body+='\n\n## '+('Known outdated records' if lang=='en' else 'Documents obsolètes identifiés')+' {#historical}\n\n'+('Older architecture notes describe French-only UI, a single worker and text-only attachments; the current app has English/French UI, parallel mission branches and rich media. Earlier split CyTools and CyProjectCodex are compatibility registrations. Machine-specific Ollama examples are examples, not hardware requirements. Read the current guide and code before applying old setup commands.' if lang=='en' else 'Les anciennes notes d’architecture décrivent une interface française, un worker unique et des pièces jointes textuelles ; l’application actuelle gère anglais/français, branches parallèles et médias. Les anciens CyTools séparés et CyProjectCodex sont des intégrations de compatibilité. Les exemples Ollama liés à une machine ne sont pas des prérequis matériels. Vérifiez le guide et le code actuels avant d’appliquer leurs commandes.')
        body+='\n\n## '+('Literal repository references' if lang=='en' else 'Références au dépôt conservées en texte')+' {#repository-paths}\n\n'+('\n'.join('- `'+x['source']+'`: `'+x['target']+'`' for x in unresolved) or ('None.' if lang=='en' else 'Aucune.'))
        (STAGE/'manual'/lang/'migration-inventory.md').write_text(front('migration-inventory',title,title,'Maintenance',240,body,translated=lang=='fr'),'utf-8')
    (STAGE/'inventory.json').write_text(json.dumps({'documents':inventory,'sourceFiles':SOURCE_FILES,'literalReferences':unresolved},ensure_ascii=False,indent=2)+'\n','utf-8')
    return inventory
if __name__=='__main__':print('Prepared',len(prepare()),'references/resources')
