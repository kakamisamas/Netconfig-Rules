import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from dns import build_dns
from merge import parse


class DNSArtifactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domestic = '\n'.join('DOMAIN-SUFFIX,site%d.cn' % i for i in range(50_000))
        cls.domestic += '\n' + '\n'.join('DOMAIN-SUFFIX,' + s for s in
            ('cn', 'bilibili.com', 'hdslb.com', 'qq.com', 'jd.com', 'shared.example', 'ai.example', 'doh.pub', 'ts.net'))

    def test_claude_overlap_and_bootstrap_never_enter_domestic_plugin(self):
        files = build_dns({'Domestic': self.domestic, 'Claude': 'DOMAIN-SUFFIX,ai.example\n',
                           'Steam': 'DOMAIN,login.shared.example\n'}, {})
        plugin = files['dns/Netconfig-DNS.lpx']
        self.assertIn('*.ai.example = server:https://1.1.1.1/dns-query', plugin)
        for excluded in ('ai.example', 'doh.pub', 'ts.net'):
            self.assertNotIn(excluded + ' = server:https://doh.pub/dns-query', plugin)
        self.assertIn('DOMAIN,login.shared.example', files['rules/DNS-Proxy.list'])
        self.assertNotIn('DOMAIN-SUFFIX,shared.example', files['rules/DNS-Proxy.list'])
        self.assertIn('*.shared.example = server:https://doh.pub/dns-query', plugin)
        self.assertIn('*.bilibili.com = server:https://doh.pub/dns-query', plugin)
        self.assertEqual([l for l in plugin.splitlines() if l.startswith('[')], ['[Host]'])

    def test_cn_proxy_children_never_remove_domestic_tld_or_capture_wechat(self):
        files = build_dns({'Domestic': self.domestic, 'Claude': 'DOMAIN-SUFFIX,ai.example\n',
            'Steam': 'DOMAIN-SUFFIX,csgo.wmsj.cn\nDOMAIN,lv.queniujq.cn\n'},
            {'YouTube': 'DOMAIN-SUFFIX,ggpht.cn\n'})
        plugin = files['dns/Netconfig-DNS.lpx']
        exceptions = files['rules/DNS-Proxy.list'].splitlines()
        self.assertIn('*.cn = server:https://doh.pub/dns-query', plugin)
        self.assertNotIn('DOMAIN-SUFFIX,cn', exceptions)
        for row in ('DOMAIN-SUFFIX,csgo.wmsj.cn', 'DOMAIN,lv.queniujq.cn', 'DOMAIN-SUFFIX,ggpht.cn'):
            self.assertIn(row, exceptions)
        # Explicit foreign exceptions must precede their domestic parent maps.
        self.assertLess(plugin.index('*.ggpht.cn = server:https://1.0.0.1/dns-query'),
                        plugin.index('*.cn = server:https://doh.pub/dns-query'))

    def test_broad_upstream_proxy_rule_aborts_instead_of_replacing_domestic_tld(self):
        with self.assertRaisesRegex(ValueError, 'top-level'):
            build_dns({'Domestic': self.domestic, 'Claude': 'DOMAIN,ai.example',
                       'Steam': 'DOMAIN-SUFFIX,cn'}, {})

    def test_claude_mapping_wins_duplicate_foreign_keys(self):
        files = build_dns({'Domestic': self.domestic, 'Claude': 'DOMAIN-SUFFIX,ai.example\n',
                           'Other': 'DOMAIN-SUFFIX,ai.example\nDOMAIN-KEYWORD,claude'}, {})
        plugin = files['dns/Netconfig-DNS.lpx']
        maps = [line.split(' = ', 1) for line in plugin.splitlines() if ' = server:' in line]
        self.assertEqual(len(maps), len(dict(maps)))
        self.assertEqual(dict(maps)['*.ai.example'], 'server:https://1.1.1.1/dns-query')

    def test_exact_exception_does_not_remove_its_domestic_subdomains(self):
        files = build_dns({'Domestic': self.domestic, 'Claude': 'DOMAIN,ai.example',
                          'Steam': 'DOMAIN,shared.example'}, {})
        maps = dict(line.split(' = ', 1) for line in files['dns/Netconfig-DNS.lpx'].splitlines()
                    if ' = server:' in line)
        self.assertEqual(maps['shared.example'], 'server:https://1.0.0.1/dns-query')
        self.assertEqual(maps['*.shared.example'], 'server:https://doh.pub/dns-query')

    def test_real_snapshots_keep_cn_coverage_and_unchanged_claude_maps(self):
        import json
        from dns import domain_rows
        root = Path(__file__).resolve().parents[1]
        sources = json.loads((root / 'sources.json').read_text())
        bundles = {b['name']: (root / ('rules/' + b['name'] + '.list')).read_text()
                   for b in sources['bundles']}
        exclusions = {s['id']: (root / ('upstream/' + s['id'] + '.list')).read_text()
                      for s in sources['dns_exclusions']}
        files = build_dns(bundles, exclusions)
        maps = dict(line.split(' = ', 1) for line in files['dns/Netconfig-DNS.lpx'].splitlines()
                    if ' = server:' in line)
        self.assertEqual(maps['*.cn'], 'server:https://doh.pub/dns-query')
        self.assertEqual(maps['*.qq.com'], 'server:https://doh.pub/dns-query')
        emitted = set(domain_rows(files['rules/DNS-Proxy.list']))
        declared = {row for name, text in bundles.items() if name != 'Domestic' for row in domain_rows(text)}
        declared.update(row for text in exclusions.values() for row in domain_rows(text))
        self.assertEqual(emitted, declared, 'DNS exceptions must preserve original match scope')
        old = (root / 'dns/Netconfig-DNS.lpx').read_text().splitlines()
        old_claude = {line for line in old if 'server:https://1.1.1.1/dns-query' in line}
        new_claude = {line for line in files['dns/Netconfig-DNS.lpx'].splitlines()
                      if 'server:https://1.1.1.1/dns-query' in line}
        self.assertEqual(old_claude, new_claude)

    def test_unknown_upstream_and_abnormal_shrink_abort(self):
        with self.assertRaises(ValueError):
            parse('DOMAIN-REGEX,.*', 'new')
        with self.assertRaises(ValueError):
            build_dns({'Domestic': self.domestic, 'Claude': 'DOMAIN,ai.example'}, {},
                      {'domestic_source_rules': 100_000})

    def test_only_declared_non_dns_syntax_is_ignored(self):
        rows, _ = parse('USER-AGENT,YouTube*\nDOMAIN-SUFFIX,youtube.com', 'media', True)
        self.assertEqual(len(rows), 2)
        with self.assertRaises(ValueError):
            parse('USER-AGENT,YouTube*', 'business')


if __name__ == '__main__':
    unittest.main()
