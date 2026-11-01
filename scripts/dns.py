"""Derive DNS artifacts from the same public rule snapshots as business rules."""
import hashlib
import json
CLAUDE = 'https://1.1.1.1/dns-query'
DOMESTIC = 'https://doh.pub/dns-query'
ORDINARY = 'https://1.0.0.1/dns-query'


def domain_rows(text):
    for raw in text.splitlines():
        row = raw.strip()
        if not row or row.startswith(('#', ';')):
            continue
        kind, value, *_ = row.split(',')
        if kind in {'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD'}:
            yield kind, value.lower()


def host_patterns(rows):
    patterns = set()
    for kind, value in rows:
        if kind == 'DOMAIN':
            patterns.add(value)
        elif kind == 'DOMAIN-SUFFIX':
            patterns.update((value, '*.' + value))
        else:
            patterns.add('*' + value + '*')
    return patterns


def build_dns(bundles, exclusions, previous=None):
    """Keep domestic parents and emit only the declared proxy exceptions.

    A proxy child never turns its parent (especially a TLD) into an exception.
    Loon receives explicit foreign Host mappings before domestic parent maps;
    Mihomo uses the same foreign conditions before the Domestic rule-provider.
    """
    domestic = list(domain_rows(bundles['Domestic']))
    if any(k == 'DOMAIN-KEYWORD' for k, _ in domestic) or len(domestic) < 50_000:
        raise ValueError('Unexpected Domestic syntax or list size; retain previous publication')
    if previous and len(domestic) < previous['domestic_source_rules'] * 0.9:
        raise ValueError('Domestic source shrank by more than 10%; manual review required')
    claude = list(domain_rows(bundles['Claude']))
    if not claude:
        raise ValueError('Empty Claude domain coverage')
    protected = [row for name, text in bundles.items() if name != 'Domestic'
                 for row in domain_rows(text)]
    protected += [row for text in exclusions.values() for row in domain_rows(text)]
    protected = list(dict.fromkeys(protected))
    if any(kind == 'DOMAIN-SUFFIX' and '.' not in value
           and any(domain == value or domain.endswith('.' + value) for _, domain in domestic)
           for kind, value in protected):
        raise ValueError('Proxy top-level suffix would capture unrelated domestic domains')
    exact, suffixes, keywords = set(), set(), set()
    for kind, value in protected:
        if kind == 'DOMAIN':
            exact.add(value)
        elif kind == 'DOMAIN-SUFFIX':
            suffixes.add(value)
        else:
            keywords.add(value)
    # Bootstrap and private DNS remain owned by the client configuration.
    exact.add('doh.pub')
    suffixes.add('ts.net')
    safe = []
    for kind, domain in domestic:
        labels = domain.split('.')
        conflict = (domain == 'doh.pub' or kind == 'DOMAIN' and domain in exact
                    or any('.'.join(labels[i:]) in suffixes for i in range(len(labels)))
                    or any(word in domain for word in keywords))
        if not conflict:
            safe.append((kind, domain))
    if not safe:
        raise ValueError('Empty domestic DNS coverage')
    if ('DOMAIN-SUFFIX', 'cn') in domestic and ('DOMAIN-SUFFIX', 'cn') not in safe:
        raise ValueError('Domestic .cn fallback disappeared; retain previous publication')
    domestic_patterns, claude_patterns = host_patterns(safe), host_patterns(claude)
    domestic_patterns -= claude_patterns
    for sample in ('bilibili.com', 'hdslb.com', 'qq.com', 'jd.com'):
        if not any(k == 'DOMAIN-SUFFIX' and (sample == d or sample.endswith('.' + d))
                   or k == 'DOMAIN' and sample == d for k, d in safe):
            raise ValueError('Domestic regression: ' + sample)
    plugin = ['#!name = Netconfig DNS 分流',
              '#!desc = 同源规则生成：国内腾讯 DoH、Claude Cloudflare DoH，其余沿用主配置。出口由主配置决定。',
              '#!author = kakamisamas', '#!homepage = https://github.com/kakamisamas/Netconfig-Rules',
              '# Source hashes: see dns/manifest.json', '', '[Host]']
    # High-priority entries are emitted first, and duplicate keys cannot replace
    # Claude's residential DNS. Never infer a parent exception from a child.
    foreign_patterns = host_patterns(protected) - claude_patterns
    domestic_patterns -= foreign_patterns
    plugin += [p + ' = server:' + CLAUDE for p in sorted(claude_patterns)]
    plugin += [p + ' = server:' + ORDINARY for p in sorted(foreign_patterns)]
    plugin += [p + ' = server:' + DOMESTIC for p in sorted(domestic_patterns)]
    plugin_text = '\n'.join(plugin) + '\n'
    exceptions = '# Declared proxy DNS conditions only; never expand to ancestor domains.\n'
    exceptions += '\n'.join(k + ',' + d for k, d in sorted(protected)) + '\n'
    files = {'dns/Netconfig-DNS.lpx': plugin_text,
             'rules/DNS-Proxy.list': exceptions}
    manifest = {'domestic_source': 'rules/Domestic.list',
                'domestic_source_rules': len(domestic), 'domestic_dns_rules': len(safe),
                'domestic_dns_host_mappings': len(domestic_patterns),
                'claude_dns_host_mappings': len(claude_patterns),
                'foreign_overlap_rules': len(protected),
                'foreign_dns_host_mappings': len(foreign_patterns),
                'derivation_version': 2,
                'query_routes': {'domestic': 'DIRECT', 'ordinary': 'client-selected', 'claude': 'client-residential'},
                'source_sha256': {**{n: hashlib.sha256(t.encode()).hexdigest() for n, t in bundles.items()},
                                  **{n: hashlib.sha256(t.encode()).hexdigest() for n, t in exclusions.items()}},
                'output_sha256': {p: hashlib.sha256(t.encode()).hexdigest() for p, t in files.items()}}
    files['dns/manifest.json'] = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'
    return files
