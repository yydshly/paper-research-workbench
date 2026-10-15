import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from adapters.europe_pmc import EuropePMC
from apps.workbench.server import make_server
from apps.workbench.service import Workbench


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = b'{"hitCount":0,"version":"fixture","resultList":{"result":[]}}'
        cls.server = make_server(0, Workbench(EuropePMC(transport=lambda _: fixture, interval=0)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def request(self, path, data=None, headers=None):
        headers = {"Content-Type": "application/json", **(headers or {})}
        req = Request(self.base + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        try:
            with urlopen(req) as res: return res.status, res.headers, res.read()
        except HTTPError as res:
            return res.code, res.headers, res.read()

    def test_page_and_docs(self):
        status, headers, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'lang="zh-CN"', body)
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertEqual(self.request('/api/docs/requirements')[0], 200)

    def test_search_empty_and_invalid(self):
        status, _, body = self.request('/api/search', {"query":"nothing", "count":50})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["papers"], [])
        self.assertEqual(self.request('/api/search', {"query":""})[0], 400)

    def test_model_explicit_503(self):
        status, _, body = self.request('/api/explain', {})
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)['error']['code'], 'MODEL_NOT_CONNECTED')

    def test_local_boundary_and_traversal(self):
        self.assertEqual(self.request('/api/search', {"query":"x"}, {"Origin":"https://untrusted.example"})[0],403)
        self.assertEqual(self.request('/', headers={"Host":"untrusted.example"})[0],403)
        self.assertEqual(self.request('/%2e%2e/%2e%2e/service.py')[0],404)
        self.assertEqual(self.request('/api/docs/../../README')[0],404)


if __name__ == '__main__': unittest.main()
