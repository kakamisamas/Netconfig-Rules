import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import merge


class MergeTests(unittest.TestCase):
    def test_other_ai_accepts_the_upstream_wildcard(self):
        row = 'DOMAIN-WILDCARD,scontent-*.xx.fbcdn.net'
        self.assertEqual(merge.parse(row, 'AI-Other-AI')[0], [row])
        with self.assertRaises(ValueError):
            merge.parse('DOMAIN-WILDCARD,*.cn', 'unsafe')

    def test_bad_source_uses_its_snapshot_and_other_rules_still_publish(self):
        for failure in ('unsupported', 'empty', 'download', 'dns'):
            with self.subTest(failure=failure), TemporaryDirectory() as temporary:
                root = Path(temporary)
                names = ('Domestic', 'Claude', 'Other-AI', 'Steam')
                sources = {
                    'bundles': [
                        {'name': name, 'sources': [{'id': name, 'url': name}]}
                        for name in names
                    ],
                    'dns_exclusions': [],
                }
                (root / 'sources.json').write_text(json.dumps(sources))
                (root / 'upstream').mkdir()
                domestic = ''.join(f'DOMAIN-SUFFIX,site{n}.cn\n' for n in range(50_000))
                domestic += ''.join(f'DOMAIN-SUFFIX,{host}\n'
                                    for host in ('bilibili.com', 'hdslb.com', 'qq.com', 'jd.com', 'cn'))
                previous = {
                    'Domestic': domestic,
                    'Claude': 'DOMAIN,ai.example\n',
                    'Other-AI': 'DOMAIN,previous.example\n',
                    'Steam': 'DOMAIN,old.steam.example\n',
                }
                for source, content in previous.items():
                    (root / 'upstream' / (source + '.list')).write_text(content)
                candidate = {
                    **previous,
                    'Other-AI': {
                        'unsupported': 'DOMAIN-REGEX,.*\n',
                        'empty': '',
                        'download': OSError('connection reset'),
                        'dns': 'DOMAIN-SUFFIX,cn\n',
                    }[failure],
                    'Steam': 'DOMAIN,new.steam.example\n',
                }

                def fetch(source):
                    result = candidate[source]
                    if isinstance(result, OSError):
                        raise result
                    return result

                log = io.StringIO()
                with patch.object(merge, 'ROOT', root), patch.object(merge, 'fetch', fetch), redirect_stdout(log):
                    merge.main()
                self.assertIn('previous snapshot for Other-AI', log.getvalue())
                self.assertEqual((root / 'upstream/Other-AI.list').read_text(), previous['Other-AI'])
                self.assertIn('DOMAIN,previous.example', (root / 'rules/Other-AI.list').read_text())
                self.assertIn('DOMAIN,new.steam.example', (root / 'rules/Steam.list').read_text())
                self.assertIn('DOMAIN,new.steam.example', (root / 'rules/DNS-Proxy.list').read_text())
                self.assertNotIn('DOMAIN-SUFFIX,cn\n', (root / 'rules/DNS-Proxy.list').read_text())
