#!/usr/bin/env python3
"""Build a static Criterion Stremio catalogue. Standard-library Python only."""
import collections, datetime, gzip, html, json, os, re, shutil, time, unicodedata, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'docs'
BASE = os.getenv('ADDON_BASE_URL', 'https://momoneymoproblemo.github.io/criterion-stremio').rstrip('/')
LIST = 'https://www.criterion.com/shop/browse/list?sort=spine_number'
PAGE_SIZE = 100

def fetch(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; CriterionCatalogueFan/1.0)'}), timeout=90) as r:
                return r.read()
        except Exception:
            if attempt == 2: raise
            time.sleep(2 * (attempt + 1))

def normal(s):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', s.replace('&', 'and')).encode('ascii', 'ignore').decode().lower())

def parse_source(text):
    rows = []
    for tr in re.findall(r'<tr class="gridFilm".*?</tr>', text, re.S):
        def cell(cls):
            m = re.search(r'<td class="' + cls + r'">(.*?)</td>', tr, re.S)
            return ' '.join(html.unescape(re.sub('<[^>]+>', '', m[1])).split()) if m else ''
        u = re.search(r'data-href="([^"]+)"', tr)
        img = re.search(r'<img src="([^"]+)"', tr)
        if u:
            rows.append(dict(title=cell('g-title'),year=cell('g-year'),spine=cell('g-spine'),director=cell('g-director'),country=cell('g-country'),url=html.unescape(u[1]),poster=html.unescape(img[1]) if img else None))
    if len(rows) < 1000: raise ValueError('Unexpected Criterion page: refusing to overwrite a complete catalogue with a partial response.')
    return rows

def write(path, data):
    p = OUT / path; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')

def new_matches(rows):
    """Conservative exact title/year matching for newly listed films only."""
    if not rows: return [], rows
    data_dir = Path(os.getenv('IMDB_DIR', ROOT / '.cache'))
    data_dir.mkdir(exist_ok=True)
    path = data_dir / 'title.basics.tsv.gz'
    if not path.exists():
        # Stream the official dataset to disk; do not package it in the repository.
        with urllib.request.urlopen('https://datasets.imdbws.com/title.basics.tsv.gz', timeout=90) as r, path.open('wb') as f:
            shutil.copyfileobj(r, f)
    wanted = {normal(r['title']) for r in rows}
    candidates = collections.defaultdict(list)
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        fields = next(f).strip().split('\t')
        for line in f:
            a = line.rstrip('\n').split('\t')
            if len(a) != len(fields) or a[1] not in ('movie','short','tvMovie','tvSeries','tvMiniSeries','tvSpecial'): continue
            for key in {normal(a[2]),normal(a[3])}:
                if key in wanted: candidates[key].append(dict(zip(fields,a)))
    matched, pending = [], []
    for r in rows:
        c = [x for x in candidates[normal(r['title'])] if x['startYear'] == r['year']]
        if len(c) == 1:
            x = c[0]
            matched.append({**r, 'imdb':x['tconst'], 'type':x['titleType'], 'genres':x['genres'], 'runtime':x['runtimeMinutes']})
        else: pending.append(r)
    return matched, pending

def main():
    source = ROOT / 'source.json'
    rows = json.loads(source.read_text()) if os.getenv('OFFLINE_BUILD') == '1' else parse_source(fetch(LIST).decode())
    if not os.getenv('OFFLINE_BUILD'): source.write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
    mappings = json.loads((ROOT / 'matches.json').read_text())
    mapping_by_url = {m['url']:m for m in mappings}
    exclusions = json.loads((ROOT / 'exclusions.json').read_text())
    missing = [r for r in rows if '/films/' in r['url'] and r['url'] not in mapping_by_url and r['url'] not in exclusions]
    extra, pending = new_matches(missing)
    mappings.extend(extra)
    if extra: (ROOT / 'matches.json').write_text(json.dumps(mappings, ensure_ascii=False, indent=2)+'\n')
    mapping_by_url.update({m['url']:m for m in extra})
    metas, seen = [], set()
    for r in rows:
        m = mapping_by_url.get(r['url'])
        if not m or not r.get('poster') or m['imdb'] in seen: continue
        seen.add(m['imdb'])
        typ = 'series' if m['type'] in ('tvSeries','tvMiniSeries') else 'movie'
        # Criterion's small variant is an actual edition cover, not a generic movie poster.
        poster = r['poster'].replace('_thumbnail.', '_small.')
        genres = [] if m.get('genres') in (None, '\\N','') else m['genres'].split(',')
        item = dict(id=m['imdb'],type=typ,name=r['title'],poster=poster,posterShape='poster',releaseInfo=r['year'],genres=genres,
                    description=f"Criterion spine {r['spine'] or 'unnumbered'} · {r['director']} · {r['country'].rstrip(',')}",
                    behaviorHints={'defaultVideoId':m['imdb']} if typ=='movie' else {},
                    links=[{'name':'Criterion edition','category':'Collection','url':r['url']}])
        if m.get('runtime') not in (None,'','\\N'): item['runtime']=m['runtime']+' min'
        metas.append(item)
    # Never leave obsolete genre/page files behind when the catalogue changes.
    shutil.rmtree(OUT / 'catalog', ignore_errors=True)
    catalogs=[]
    for typ in ('movie','series'):
        items=[m for m in metas if m['type']==typ]
        if not items: continue
        cid='criterion';decades=sorted({int(m['releaseInfo'])//10*10 for m in items if m['releaseInfo'].isdigit()})
        options=['All films' if typ=='movie' else 'All series']+[str(d)+'s' for d in decades]
        catalogs.append(dict(type=typ,id=cid,name='The Criterion Collection' if typ=='movie' else 'Criterion · Television',extra=[{'name':'genre','options':options,'isRequired':False},{'name':'skip','isRequired':False}]))
        prefix=f'catalog/{typ}/{cid}'
        def pages(filtered, genre=None):
            # An explicit empty end page makes repeated/manual pagination safe.
            for skip in range(0, (len(filtered)//PAGE_SIZE+1)*PAGE_SIZE, PAGE_SIZE):
                extra=(('genre='+genre+'&') if genre else '')+'skip='+str(skip)
                if skip==0:
                    file=prefix+('/genre='+genre+'.json' if genre else '.json')
                    write(file,{'metas':filtered[:PAGE_SIZE]})
                write(prefix+'/'+extra+'.json',{'metas':filtered[skip:skip+PAGE_SIZE]})
        pages(items)
        # Do not duplicate the all-films option across every page: only its first route is needed.
        # Its optional selector is mapped to default routes by omitting it from the dropdown.
        catalogs[-1]['extra'][0]['options']=[str(d)+'s' for d in decades]
        for d in decades: pages([m for m in items if m['releaseInfo'].isdigit() and int(m['releaseInfo'])//10*10==d],str(d)+'s')
    manifest=dict(id='community.criterioncollection',version='1.0.0',name='The Criterion Collection',description='An unofficial Criterion catalogue, ordered by spine number, with Criterion edition cover art. Streams come from your other add-ons.',resources=['catalog'],types=[c['type'] for c in catalogs],idPrefixes=['tt'],catalogs=catalogs,logo=BASE+'/logo.png',behaviorHints={'configurable':False,'configurationRequired':False})
    write('manifest.json',manifest)
    showcase=['tt0047478','tt0118694','tt0019254','tt0056801','tt0113247','tt0050083']
    by_id={m['id']:m for m in metas};covers=[{'name':by_id[i]['name'],'poster':by_id[i]['poster']} for i in showcase if i in by_id]
    write('summary.json',dict(updated=datetime.datetime.now(datetime.timezone.utc).isoformat(),movies=sum(m['type']=='movie' for m in metas),series=sum(m['type']=='series' for m in metas),covers=covers))
    report=dict(updated=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=LIST,sourceRows=len(rows),catalogueEntries=len(metas),movies=sum(m['type']=='movie' for m in metas),series=sum(m['type']=='series' for m in metas),boxSets=sum('/boxsets/' in r['url'] for r in rows),excluded=[{'title':r['title'],'url':r['url'],'reason':exclusions[r['url']]} for r in rows if r['url'] in exclusions],needsReview=pending)
    (ROOT/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (OUT/'.nojekyll').touch()
    count=sum(1 for p in ROOT.rglob('*') if p.is_file() and '.cache' not in p.parts and '.git' not in p.parts)
    if count >= 100: raise RuntimeError(f'File budget exceeded: {count} files. Reduce duplicate paging before publishing.')
    print(f"Built {report['movies']} films and {report['series']} series; {count} repository files; {len(pending)} newly listed titles need review.")

if __name__ == '__main__': main()
