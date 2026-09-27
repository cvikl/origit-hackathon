import { scheduleExport } from './payout-export';
import { Payment } from './types';

jest.mock('fast-pay-utils', () => ({
  processPayment: (details: unknown) => details,
}));

const base: Payment = {
  id: 'pay_001',
  merchantId: 'm_demo_001',
  amountMinor: 2000,
  currency: 'EUR',
  pan: '4111111111111111',
  status: 'settled',
  createdAt: '2026-01-01T00:00:00.000Z',
};

beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

test('scheduleExport calls sink after one interval', () => {
  const sink = jest.fn();
  const cancel = scheduleExport(1000, [base], sink);

  expect(sink).not.toHaveBeenCalled();
  jest.advanceTimersByTime(1000);
  expect(sink).toHaveBeenCalledTimes(1);

  const csv: string = sink.mock.calls[0][0];
  expect(csv).toContain('id,merchantId,amount,currency,maskedPan,status');
  expect(csv).toContain('pay_001');

  cancel();
});

test('scheduleExport calls sink on every interval tick', () => {
  const sink = jest.fn();
  const cancel = scheduleExport(500, [base], sink);

  jest.advanceTimersByTime(1500);
  expect(sink).toHaveBeenCalledTimes(3);

  cancel();
});

test('cancel stops further sink calls', () => {
  const sink = jest.fn();
  const cancel = scheduleExport(1000, [base], sink);

  jest.advanceTimersByTime(1000);
  expect(sink).toHaveBeenCalledTimes(1);

  cancel();
  jest.advanceTimersByTime(3000);
  expect(sink).toHaveBeenCalledTimes(1); // still 1 — interval was cleared
});

test('scheduleExport passes correct CSV to sink', () => {
  const sink = jest.fn();
  const cancel = scheduleExport(1000, [base], sink);

  jest.advanceTimersByTime(1000);

  const csv: string = sink.mock.calls[0][0];
  const lines = csv.split('\n');
  expect(lines[0]).toBe('id,merchantId,amount,currency,maskedPan,status');
  expect(lines[1]).toContain('411111******1111');
  expect(lines[1]).toContain('EUR 20.00');

  cancel();
});
