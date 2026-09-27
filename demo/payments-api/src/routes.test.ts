import request from 'supertest';
import { createApp } from './index';
import * as store from './store';

const app = createApp();

beforeEach(() => {
  store.clear();
});

const validBody = {
  merchantId: 'm_demo_001',
  amountMinor: 1000,
  currency: 'EUR',
  pan: '4111111111111111',
};

test('GET /health returns ok', async () => {
  const res = await request(app).get('/health');
  expect(res.status).toBe(200);
  expect(res.body).toEqual({ ok: true });
});

test('POST /payments returns 201 with id', async () => {
  const res = await request(app).post('/payments').send(validBody);
  expect(res.status).toBe(201);
  expect(res.body).toHaveProperty('id');
  expect(typeof res.body.id).toBe('string');
});

test('GET /payments/:id returns the payment', async () => {
  const created = await request(app).post('/payments').send(validBody);
  const id = created.body.id as string;
  const res = await request(app).get(`/payments/${id}`);
  expect(res.status).toBe(200);
  expect(res.body.id).toBe(id);
  expect(res.body.merchantId).toBe(validBody.merchantId);
});

test('GET /payments/:id returns 404 for unknown id', async () => {
  const res = await request(app).get('/payments/does-not-exist');
  expect(res.status).toBe(404);
});
