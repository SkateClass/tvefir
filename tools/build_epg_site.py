#!/usr/bin/env python3
"""EFIR: download XMLTV, build same-origin epg.json, preserve the existing remote."""
import argparse, datetime as dt, gzip, io, json, os, re, shutil, sys, urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET
SOURCES=[
    'https://epg.pw/xmltv/epg_RU.xml',
    'https://iptvx.one/epg/epg_lite.xml.gz',
    'https://xmltv.live/epg/ru.xml.gz',
    'https://iptv-epg.org/files/epg-ru.xml',
]
def stamp(value):
    m=re.fullmatch(r'(\d{12}|\d{14})\s*([+-]\d{4})',str(value or '').strip())
    if not m:return None
    try:
        fmt='%Y%m%d%H%M%S%z' if len(m[1])==14 else '%Y%m%d%H%M%z'
        return int(dt.datetime.strptime(''.join(m.groups()),fmt).timestamp()*1000)
    except ValueError:return None

def parse_xml(raw,url,now=None):
    if raw[:2]==b'\x1f\x8b':
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:raw=f.read(100_000_001)
    if len(raw)>100_000_000:raise ValueError('Uncompressed XMLTV exceeds 100 MB')
    if b'<!ENTITY' in raw.upper():raise ValueError('XML entity declarations not permitted')
    root=ET.fromstring(raw)
    if root.tag!='tv':raise ValueError('Response is not XMLTV')
    now=now or int(dt.datetime.now(dt.timezone.utc).timestamp()*1000)
    channels={}
    for c in root.findall('channel'):
        cid=c.get('id')
        if not cid:continue
        names=[(n.text or '').strip() for n in c.findall('display-name') if (n.text or '').strip()]
        channels[cid]={'id':cid,'names':names or [cid],'programmes':[]}
    for p in root.findall('programme'):
        c=channels.get(p.get('channel'))
        if c is None:continue
        start,stop=stamp(p.get('start')),stamp(p.get('stop'))
        ts=p.findall('title');ru=next((t for t in ts if t.get('lang','').lower().startswith('ru')),None)
        title=((ru if ru is not None else ts[0]).text or '').strip() if ts else ''
        if start is not None and title and now-86400000<start<now+3*86400000 and (stop is None or stop>now-3600000):
            c['programmes'].append({'start':start,'stop':stop,'title':title})
    out=[]
    for c in channels.values():
        ps=sorted(c['programmes'],key=lambda p:p['start'])
        next_start=None
        for p in reversed(ps):
            if p['stop'] is None and next_start is not None and next_start>p['start']:p['stop']=next_start
            if next_start is None or p['start']<next_start:next_start=p['start']
        unique={(p['start'],p['stop'],p['title']):p for p in ps if p['stop'] is not None and p['stop']>p['start'] and p['stop']>now-3600000}
        c['programmes']=sorted(unique.values(),key=lambda p:p['start'])
        if c['programmes']:out.append(c)
    if not out or not any(p['stop']>now for c in out for p in c['programmes']):raise ValueError('No current/future programmes with timezone information')
    return {'url':url,'channels':out}

def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; EFIR-EPG/1.0)','Accept-Encoding':'identity'})
    with urllib.request.urlopen(request,timeout=50) as r:
        raw=r.read(35_000_001)
    if len(raw)>35_000_000:raise ValueError('Download exceeds 35 MB')
    return raw

def inject(html,addon):
    if not re.search(r'id\s*=\s*[\"\x27]grid[\"\x27]',html,re.I):raise ValueError('tvpult.html: channel grid id="grid" not found; original not modified')
    if not re.search(r'</body\s*>',html,re.I):raise ValueError('tvpult.html is incomplete')
    # Remove only previously generated EPG blocks, not the original player code.
    for tag,ident in [('script','efir-programme-script'),('style','efir-programme-style'),('script','efir-epg-addon-v1'),('script','efir-epg-pages-v1')]:
        pattern=r'<'+tag+r'\b(?=[^>]*\bid\s*=\s*[\"\x27]'+re.escape(ident)+r'[\"\x27])[^>]*>.*?</'+tag+r'\s*>\s*'
        html=re.sub(pattern,'',html,flags=re.I|re.S)
    if '</script' in addon.lower():raise ValueError('Unsafe embedded addon terminator')
    block='\n<script id="efir-epg-pages-v1">\n'+addon+'\n</script>\n'
    return re.sub(r'</body\s*>',lambda m:block+m.group(0),html,count=1,flags=re.I)

def stage(root,out,addon,epg):
    root=Path(root).resolve();out=Path(out).resolve()
    if root==out or out in root.parents:raise ValueError('Invalid output directory')
    if out.exists():shutil.rmtree(out)
    out.mkdir(parents=True)
    # Keep existing static files and URLs. Never publish workflow/git internals.
    for p in root.rglob('*'):
        rel=p.relative_to(root)
        if p.is_symlink() or out in p.parents or p==out:continue
        if any(x in {'.git','.github','__pycache__','node_modules','.venv','tools','_site'} for x in rel.parts):continue
        if p.is_file():
            target=out/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    original=(root/'tvpult.html').read_text(encoding='utf-8-sig')
    changed=inject(original,addon)
    (out/'tvpult.html').write_text(changed,encoding='utf-8')
    (out/'epg.json').write_text(json.dumps(epg,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (out/'.nojekyll').touch()
    # Test entry bypasses prior PWA caches; the normal tvpult URL remains unchanged.
    test=changed
    # Only in the extra test copy, disable automatic registration of the old SW.
    test=re.sub(r"if\(\s*['\"]serviceWorker['\"]\s+in\s+navigator\s*&&\s*location\.protocol\s*===\s*['\"]https:['\"]\s*\)", 'if(false)',test)
    (out/'tvpult-epg-test.html').write_text(test,encoding='utf-8')
    print(json.dumps({'page':'tvpult.html','testPage':'tvpult-epg-test.html','feeds':len(epg['feeds']),'channels':sum(len(f['channels']) for f in epg['feeds']),'originalSourceBytes':len(original.encode('utf-8'))},ensure_ascii=False))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default='.');ap.add_argument('--out',default='_site');ap.add_argument('--xmltv-file');a=ap.parse_args()
    root=Path(a.root);addon=(root/'tools/epg-cards.js').read_text(encoding='utf-8')
    if not (root/'tvpult.html').is_file():raise SystemExit('tvpult.html must exist at repository root')
    feeds=[];errors=[]
    if a.xmltv_file:feeds=[parse_xml(Path(a.xmltv_file).read_bytes(),'local-test')]
    else:
        for url in SOURCES:
            try:
                f=parse_xml(fetch(url),url);feeds.append(f);print('OK:',url,'channels:',len(f['channels']))
                # Two independent successful sources are enough for the first rollout.
                if len(feeds)>=2:break
            except Exception as e:errors.append({'source':url,'error':str(e)});print('SOURCE FAILED:',url,str(e),file=sys.stderr)
    if not feeds:raise SystemExit('No XMLTV source succeeded. Nothing deployed; previous site remains unchanged. '+json.dumps(errors,ensure_ascii=False))
    epg={'schema':1,'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'timezone':'Europe/Moscow','feeds':feeds,'sourceErrors':errors}
    stage(root,a.out,addon,epg)
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as f:
            f.write('## EFIR EPG\n\nBuild succeeded. Open `tvpult-epg-test.html` for the first test.\n\n')
            for source in feeds:f.write('- '+source['url']+': '+str(len(source['channels']))+' channels\n')
if __name__=='__main__':main()
