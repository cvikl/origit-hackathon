import { settle } from './settlement';
import { Payment } from './types';

const fakeDelay = (): Promise<void> => Promise.resolve();

const basePayment: Payment = {
  id: 'pay_test_001',
  merchantId: 'm_demo_001',
  amountMinor: 1000,
  currency: 'EUR',
  pan: '4111111111111111',
  status: 'authorised',
  createdAt: '2024-01-01T00:00:00.000Z',
};

test('settle returns settled on first try', async () => {
  const send = jest.fn().mockResolvedValue(undefined);
  const result = await settle(basePayment, send, fakeDelay);
  expect(result.status).toBe('settled');
  expect(result.id).toBe(basePayment.id);
  expect(send).toHaveBeenCalledTimes(1);
});

test('settle retries and returns settled on third try', async () => {
  const send = jest
    .fn()
    .mockRejectedValueOnce(new Error('network'))
    .mockRejectedValueOnce(new Error('network'))
    .mockResolvedValue(undefined);
  const result = await settle(basePayment, send, fakeDelay);
  expect(result.status).toBe('settled');
  expect(send).toHaveBeenCalledTimes(3);
});

test('settle returns failed after three consecutive failures', async () => {
  const send = jest.fn().mockRejectedValue(new Error('network'));
  const result = await settle(basePayment, send, fakeDelay);
  expect(result.status).toBe('failed');
  expect(result.id).toBe(basePayment.id);
  expect(send).toHaveBeenCalledTimes(3);
});
