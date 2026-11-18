#!/usr/bin/env python3
"""Publish unions of declared public rule files, never nodes or private settings."""
import concurrent.futures
import hashlib
import http.client
import ipaddress
import json
from pathlib import Path
import re
import time
from typing import NamedTuple
import urllib.error
import urllib.parse
import urllib.request

from dns import build_dns

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED = {'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'DOMAIN-WILDCARD',
             'IP-CIDR', 'IP-CIDR6', 'IP-ASN'}


class Snapshot(NamedTuple):
    text: str
    rows: list[str]
    comments: list[str]


def fetch(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme, parsed.hostname) != ('https', 'raw.githubusercontent.com') or parsed.query or parsed.username:
        raise ValueError('Source must be an anonymous public GitHub raw rule URL')
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Netconfig-Rules/1.0'})
            with urllib.request.urlopen(request, timeout=25) as response:
                content = response.read()
            return content.decode('utf-8-sig')
        except (urllib.error.URLError, OSError, http.client.HTTPException):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def parse(text, source_id, dns_exclusion=False):
    rows, comments = [], []
    for line_number, raw in enumerate(text.splitlines(), 1):
        row = raw.strip()
        if not row:
            continue
        if row.startswith(('#', ';')):
            comments.append(row)
            continue
        fields = [part.strip() for part in row.split(',')]
        allowed = SUPPORTED | ({'USER-AGENT'} if dns_exclusion else set())
        if len(fields) < 2 or fields[0] not in allowed or not fields[1]:
            raise ValueError(f'Unsupported rule in {source_id}, line {line_number}: {fields[0][:40]}')
        kind, value = fields[:2]
        if kind in ('DOMAIN', 'DOMAIN-SUFFIX') and not re.fullmatch(r'[a-zA-Z0-9_.-]+', value):
            raise ValueError('Invalid domain in ' + source_id)
        if kind == 'DOMAIN-WILDCARD' and not re.fullmatch(
            r'(?:[a-zA-Z0-9_?*-]+\.)*[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+', value
        ):
            raise ValueError(f'Unsupported or overly broad wildcard in {source_id}, line {line_number}')
        if kind in ('IP-CIDR', 'IP-CIDR6'):
            network = ipaddress.ip_network(value, strict=False)
            if network.version != (6 if kind == 'IP-CIDR6' else 4):
                raise ValueError('IP family mismatch in ' + source_id)
        if kind == 'IP-ASN' and not value.isdecimal():
            raise ValueError('Invalid ASN in ' + source_id)
        rows.append(','.join(fields))
    if not rows:
        raise ValueError('Empty source: ' + source_id)
    return rows, comments


def snapshot(text, source_id, exclusions):
    rows, comments = parse(text, source_id, source_id in exclusions)
    return Snapshot(text, rows, comments)


def previous_snapshot(source_id, exclusions):
    path = ROOT / 'upstream' / (source_id + '.list')
    try:
        return snapshot(path.read_bytes().decode('utf-8'), source_id, exclusions)
    except (OSError, ValueError) as error:
        raise RuntimeError(f'No usable published snapshot for {source_id}') from error


def warn_fallback(source_id, error):
    message = f'Using previous snapshot for {source_id}: {error}'
    escaped = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    print('::warning::' + escaped)


def load_sources(entries, exclusions):
    snapshots = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {key: executor.submit(fetch, source['url']) for key, source in entries.items()}
        for key, future in futures.items():
            try:
                snapshots[key] = snapshot(future.result(), key, exclusions)
            except (OSError, http.client.HTTPException, ValueError) as error:
                warn_fallback(key, error)
                snapshots[key] = previous_snapshot(key, exclusions)
    return snapshots


def build_publication(bundles, exclusions, snapshots, previous):
    files, manifests = {}, {}
    for bundle in bundles:
        seen, lines, records = set(), [], []
        for source in bundle['sources']:
            selected = snapshots[source['id']]
            additions = [row for row in dict.fromkeys(selected.rows) if row not in seen]
            seen.update(selected.rows)
            lines += ['', '# Upstream: ' + source['url'], '# Upstream comments retained below:']
            lines += selected.comments + additions
            records.append({**source, 'rules': len(selected.rows), 'new_unique_rules': len(additions),
                            'sha256': hashlib.sha256(selected.text.encode()).hexdigest(),
                            'snapshot': 'upstream/' + source['id'] + '.list'})
        content = '\n'.join(['# Netconfig-Rules: ' + bundle['name'],
                              '# Exact union of complete upstream lists; unique rules: ' + str(len(seen)),
                              '# Domain, keyword, CIDR, IPv6 and ASN conditions are retained.'] + lines) + '\n'
        files['rules/' + bundle['name'] + '.list'] = content
        manifests[bundle['name']] = {'rules': len(seen), 'types': sorted({r.split(',')[0] for r in seen}),
                                     'sha256': hashlib.sha256(content.encode()).hexdigest(),
                                     'filtered_rules': 0, 'sources': records}
    files.update({'upstream/' + key + '.list': selected.text for key, selected in snapshots.items()})
    files['rules/manifest.json'] = json.dumps(manifests, ensure_ascii=False, indent=2) + '\n'
    files.update(build_dns({b['name']: files['rules/' + b['name'] + '.list'] for b in bundles},
                           {key: snapshots[key].text for key in exclusions}, previous))
    return files, manifests


def recover_publication(bundles, exclusions, snapshots, previous):
    # Start with the published inputs, then keep each change that can still
    # produce a coherent rules and DNS release.
    accepted = {key: previous_snapshot(key, exclusions) for key in snapshots}
    files, manifests = build_publication(bundles, exclusions, accepted, previous)
    for key, candidate in snapshots.items():
        if candidate.text == accepted[key].text:
            continue
        trial = {**accepted, key: candidate}
        try:
            files, manifests = build_publication(bundles, exclusions, trial, previous)
        except ValueError as error:
            warn_fallback(key, error)
        else:
            accepted = trial
    return files, manifests


def main():
    settings = json.loads((ROOT / 'sources.json').read_text())
    bundles = settings['bundles']
    entries = {source['id']: source for bundle in bundles for source in bundle['sources']}
    if sum(len(bundle['sources']) for bundle in bundles) != len(entries):
        raise ValueError('Each upstream ID must be unique')
    exclusions = {source['id']: source for source in settings['dns_exclusions']}
    if set(entries) & set(exclusions):
        raise ValueError('Duplicate DNS exclusion ID')
    entries.update(exclusions)
    snapshots = load_sources(entries, exclusions)
    manifest_path = ROOT / 'dns/manifest.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    try:
        files, manifests = build_publication(bundles, exclusions, snapshots, previous)
    except ValueError:
        files, manifests = recover_publication(bundles, exclusions, snapshots, previous)

    # Publish one coherent set of validated outputs.
    for filename, content in files.items():
        path = ROOT / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    print(json.dumps({name: row['rules'] for name, row in manifests.items()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
