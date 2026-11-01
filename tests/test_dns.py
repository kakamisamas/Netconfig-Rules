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
            ('bilibili.com', 'hdslb.com', 'qq.com', 'jd.com', 'shared.example', 'ai.example', 'doh.pub', 'ts.net'))

    def test_claude_overlap_and_bootstrap_never_enter_domestic_plugin(self):
        files = build_dns({'Domestic': self.domestic, 'Claude': 'DOMAIN-SUFFIX,ai.example\n',
                           'Steam': 'DOMAIN,login.shared.example\n'}, {})
        plugin = files['dns/Netconfig-DNS.lpx']
        self.assertIn('*.ai.example = server:https://1.1.1.1/dns-query', plugin)
        for excluded in ('ai.example', 'shared.example', 'doh.pub', 'ts.net'):
            self.assertNotIn(excluded + ' = server:https://doh.pub/dns-query', plugin)
            self.assertIn('DOMAIN-SUFFIX,' + excluded, files['rules/DNS-Proxy.list'])
        self.assertIn('*.bilibili.com = server:https://doh.pub/dns-query', plugin)
        self.assertEqual([l for l in plugin.splitlines() if l.startswith('[')], ['[Host]'])

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
