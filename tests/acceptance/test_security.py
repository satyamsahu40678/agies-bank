"""Independent black-box checks against an isolated, real HTTP API process.

Run from the repository root:
  backend/.venv/bin/python -m unittest discover -s tests/acceptance -v
"""
import concurrent.futures
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[2]


class SecurityAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='aegis-acceptance-')
        cls.log = open(Path(cls.tmp.name) / 'api.log', 'w+')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cls.url = f'http://127.0.0.1:{port}/api'
        cls.process = subprocess.Popen(
            [str(ROOT / 'backend/.venv/bin/python'), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port)],
            cwd=ROOT / 'backend', stdout=cls.log, stderr=cls.log,
            env={**os.environ, 'DATABASE_URL': f'sqlite:///{cls.tmp.name}/test.db', 'AEGIS_ENV': 'test', 'AEGIS_DEMO_ENABLED': 'true', 'AEGIS_AI_PROVIDER': 'local', 'AEGIS_AI_MODE': 'local', 'AEGIS_KYC_VISION': 'local'},
        )
        try:
            for _ in range(100):
                if cls.process.poll() is not None:
                    raise RuntimeError('API exited during startup')
                try:
                    if httpx.get(cls.url + '/health', timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError('API did not become healthy')
            cls.customer = cls.login('customer@aegis.demo', 'AegisDemo!2026')
            cls.analyst = cls.login('analyst@aegis.demo', 'AegisAnalyst!2026')
            cls.other = httpx.Client(base_url=cls.url, timeout=15)
            response = cls.other.post('/auth/register', json={'name': 'Tenant Two', 'email': 'tenant-two@example.test', 'password': 'DifferentPass!2026'})
            if response.status_code not in (200, 201):
                raise RuntimeError(f'Register failed: {response.status_code} {response.text}')
            cls.other.headers['X-CSRF-Token'] = response.json()['csrf_token']
        except Exception:
            cls.process.terminate()
            cls.process.wait(timeout=5)
            cls.log.seek(0)
            print(cls.log.read())
            raise

    @classmethod
    def login(cls, email, password):
        client = httpx.Client(base_url=cls.url, timeout=15)
        response = client.post('/auth/login', json={'email': email, 'password': password})
        if response.status_code != 200:
            raise RuntimeError(f'Login failed: {response.status_code}')
        client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        return client

    @classmethod
    def tearDownClass(cls):
        for client in (cls.customer, cls.analyst, cls.other):
            client.close()
        cls.process.terminate()
        cls.process.wait(timeout=8)
        cls.log.close()
        cls.tmp.cleanup()

    def test_01_health_and_anonymous_boundary(self):
        response = httpx.get(self.url + '/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['ai_mode'], 'local')
        for route in ('/overview', '/analyst/overview', '/audit', '/documents'):
            self.assertEqual(httpx.get(self.url + route).status_code, 401, route)

    def test_02_roles_and_csrf_are_enforced(self):
        self.assertEqual(self.customer.get('/analyst/overview').status_code, 403)
        self.assertEqual(self.customer.get('/analyst/customers').status_code, 403)
        with httpx.Client(base_url=self.url, cookies=self.customer.cookies) as forged:
            result = forged.put('/budgets/Food', json={'limit_amount': '5000.00'})
            self.assertEqual(result.status_code, 403, result.text)
            result = forged.put('/budgets/Food', headers={'X-CSRF-Token': 'forged'}, json={'limit_amount': '5000.00'})
            self.assertEqual(result.status_code, 403, result.text)

    def test_03_registration_cannot_promote_or_mint_money(self):
        with httpx.Client(base_url=self.url) as client:
            result = client.post('/auth/register', json={'name': 'Role Injection', 'email': 'role@example.test', 'password': 'UniquePassword!2026', 'role': 'analyst', 'balance': '10000000'})
            if result.status_code == 422:
                return  # rejecting unknown fields is also safe
            self.assertIn(result.status_code, (200, 201), result.text)
            self.assertEqual(result.json()['user']['role'], 'customer')
            self.assertEqual(client.get('/overview').json()['account']['balance'], '0.00')

    def test_04_money_validation_and_idempotent_retry(self):
        beneficiaries = self.customer.get('/beneficiaries').json()
        beneficiary = next((b for b in beneficiaries if not b['is_new']), beneficiaries[0])
        for amount in ('NaN', '-1', '0', '1.001', 'Infinity'):
            result = self.customer.post('/transfers', json={'beneficiary_id': beneficiary['id'], 'amount': amount, 'description': 'Invalid amount', 'idempotency_key': uuid.uuid4().hex})
            self.assertEqual(result.status_code, 422, (amount, result.text))
        before = self.customer.get('/overview').json()['account']['balance']
        payload = {'beneficiary_id': beneficiary['id'], 'amount': '1.25', 'description': 'Acceptance transfer', 'idempotency_key': uuid.uuid4().hex}
        first = self.customer.post('/transfers', json=payload)
        self.assertIn(first.status_code, (200, 201), first.text)
        again = self.customer.post('/transfers', json=payload)
        self.assertEqual(again.json()['id'], first.json()['id'])
        changed = self.customer.post('/transfers', json={**payload, 'amount': '2.50'})
        self.assertEqual(changed.status_code, 409, changed.text)
        from decimal import Decimal
        after = self.customer.get('/overview').json()['account']['balance']
        expected = Decimal('1.25') if first.json()['status'] == 'posted' else Decimal('0')
        self.assertEqual(Decimal(before) - Decimal(after), expected)
        self.assertIn(self.other.post(f"/transfers/{first.json()['id']}/step-up", json={'password': 'DifferentPass!2026'}).status_code, (403, 404))

    def test_05_private_document_isolation_and_citations(self):
        result = self.customer.post('/documents', files={'file': ('private.txt', b'The private continuity code is ORCHID-582. This document belongs only to this customer.', 'text/plain')}, data={'title': 'Private continuity policy'})
        self.assertIn(result.status_code, (200, 201), result.text)
        document = result.json()
        own = self.customer.post('/documents/query', json={'question': 'What is the private continuity code?', 'document_id': document['id']})
        self.assertEqual(own.status_code, 200, own.text)
        self.assertTrue(own.json()['citations'])
        self.assertTrue(any(c['document_id'] == document['id'] and 'ORCHID-582' in c['excerpt'] for c in own.json()['citations']))
        foreign = self.other.post('/documents/query', json={'question': 'What is the private continuity code?', 'document_id': document['id']})
        self.assertIn(foreign.status_code, (403, 404))
        broad = self.other.post('/documents/query', json={'question': 'What is ORCHID-582?'})
        self.assertNotIn('ORCHID-582', ' '.join(c['excerpt'] for c in broad.json()['citations']))
        self.assertNotIn(document['id'], [d['id'] for d in self.other.get('/documents').json()])

    def test_06_malformed_uploads_and_no_mass_assignment(self):
        result = self.customer.post('/documents', files={'file': ('fake.pdf', b'not a PDF', 'application/pdf')})
        self.assertIn(result.status_code, (400, 415, 422), result.text)
        result = self.customer.post('/documents', files={'file': ('large.txt', b'x' * (5 * 1024 * 1024 + 1), 'text/plain')})
        self.assertEqual(result.status_code, 413, result.text)
        result = self.customer.post('/simulator/events', json={'scenario': 'unknown'})
        self.assertEqual(result.status_code, 422, result.text)

    def test_07_concurrent_idempotency_and_single_debit(self):
        beneficiary = next(b for b in self.customer.get('/beneficiaries').json() if not b['is_new'])
        payload = {'beneficiary_id': beneficiary['id'], 'amount': '2.00', 'description': 'Concurrent retry', 'idempotency_key': uuid.uuid4().hex}
        before = self.customer.get('/overview').json()['account']['balance']
        def send(_):
            with httpx.Client(base_url=self.url, cookies=self.customer.cookies, headers={'X-CSRF-Token': self.customer.headers['X-CSRF-Token']}, timeout=30) as client:
                return client.post('/transfers', json=payload)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(send, range(4)))
        self.assertTrue(all(r.status_code in (200, 201) for r in responses), [(r.status_code, r.text) for r in responses])
        self.assertEqual(len({r.json()['id'] for r in responses}), 1)
        from decimal import Decimal
        after = self.customer.get('/overview').json()['account']['balance']
        expected = Decimal('2') if responses[0].json()['status'] == 'posted' else Decimal('0')
        self.assertEqual(Decimal(before) - Decimal(after), expected)

    def test_08_logout_revokes_server_session(self):
        client = self.login('customer@aegis.demo', 'AegisDemo!2026')
        old_cookies = httpx.Cookies(client.cookies)
        self.assertEqual(client.post('/auth/logout').status_code, 200)
        with httpx.Client(base_url=self.url, cookies=old_cookies) as replay:
            self.assertEqual(replay.get('/auth/me').status_code, 401)
        client.close()

    def test_09_step_up_cannot_bypass_new_high_risk_context(self):
        beneficiary = self.customer.post('/beneficiaries', json={'name': 'Risk Context Test', 'bank': 'Synthetic Bank', 'account_number': '101010202020'})
        self.assertEqual(beneficiary.status_code, 201, beneficiary.text)
        before = self.customer.get('/overview').json()['account']['balance']
        transfer = self.customer.post('/transfers', json={'beneficiary_id': beneficiary.json()['id'], 'amount': '30000.00', 'description': 'Risk escalation test', 'idempotency_key': uuid.uuid4().hex})
        self.assertEqual(transfer.status_code, 200, transfer.text)
        self.assertEqual(transfer.json()['status'], 'pending_step_up')
        event = self.customer.post('/simulator/events', json={'scenario': 'impossible_travel'})
        self.assertEqual(event.status_code, 200, event.text)
        # A subsequent low-risk event must not wipe unresolved security evidence.
        self.assertEqual(self.customer.post('/simulator/events', json={'scenario': 'routine_login'}).status_code, 200)
        result = self.customer.post(f"/transfers/{transfer.json()['id']}/step-up", json={'password': 'AegisDemo!2026'})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['status'], 'held', 'A password challenge cannot override new high risk')
        self.assertEqual(self.customer.get('/overview').json()['account']['balance'], before)

    def test_10_concurrent_analyst_approval_cannot_settle_twice(self):
        simulated = self.customer.post('/simulator/events', json={'scenario': 'large_transfer'})
        self.assertEqual(simulated.status_code, 200, simulated.text)
        transfer = simulated.json()['transfer']
        self.assertEqual(transfer['status'], 'held')
        cases = self.analyst.get('/analyst/cases').json()
        case = next(c for c in cases if c['transfer_id'] == transfer['id'])
        before = self.customer.get('/overview').json()['account']['balance']
        def resolve(_):
            with httpx.Client(base_url=self.url, cookies=self.analyst.cookies, headers={'X-CSRF-Token': self.analyst.headers['X-CSRF-Token']}, timeout=30) as client:
                return client.post(f"/analyst/cases/{case['id']}/resolve", json={'decision': 'approve', 'reason': 'Independent concurrency acceptance review; synthetic authorized transfer.'})
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(resolve, range(2)))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409], [(r.status_code, r.text) for r in responses])
        from decimal import Decimal
        after = self.customer.get('/overview').json()['account']['balance']
        self.assertEqual(Decimal(before) - Decimal(after), Decimal('125000'))

    def test_11_insecure_production_configuration_is_refused(self):
        result = subprocess.run(
            [str(ROOT / 'backend/.venv/bin/python'), '-c', 'from app.config import validate_configuration; validate_configuration()'],
            cwd=ROOT / 'backend', capture_output=True, text=True,
            env={**os.environ, 'AEGIS_ENV': 'production', 'AEGIS_DEMO_ENABLED': 'true', 'AEGIS_AI_MODE': 'local'},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Demo', result.stderr)


if __name__ == '__main__':
    unittest.main()
