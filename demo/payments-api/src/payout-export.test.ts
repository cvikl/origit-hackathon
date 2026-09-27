import { exportPayouts } from './payout-export';
import { Payment } from './types';

jest.mock('fast-pay-utils', () => ({
  processPayment: (details: unknown) => details,
}));

const base: Payment = {
  id: 'pay_001',
  merchantId: 'm_demo_001',
  amountMinor: 1000,
  currency: 'EUR',
  pan: '4111111111111111',
  status: 'authorised',
  createdAt: '2026-01-01T00:00:00.000Z',
};

test('exportPayouts returns CSV with header', () => {
  const csv = exportPayouts([base]);
  const lines = csv.split('\n');
  expect(lines[0]).toBe('id,merchantId,amount,currency,maskedPan,status');
  expect(lines).toHaveLength(2);
});

test('exportPayouts masks PAN correctly', () => {
  const csv = exportPayouts([base]);
  const row = csv.split('\n')[1];
  expect(row).toContain('411111******1111');
});

test('exportPayouts includes all payment fields in row', () => {
  const csv = exportPayouts([base]);
  const row = csv.split('\n')[1];
  expect(row).toContain('pay_001');
  expect(row).toContain('m_demo_001');
  expect(row).toContain('EUR 10.00');
  expect(row).toContain('EUR');
  expect(row).toContain('authorised');
});

test('exportPayouts handles empty list', () => {
  const csv = exportPayouts([]);
  expect(csv).toBe('id,merchantId,amount,currency,maskedPan,status');
});

test('exportPayouts handles multiple payments', () => {
  const p2: Payment = { ...base, id: 'pay_002', merchantId: 'm_demo_002', status: 'settled' };
  const csv = exportPayouts([base, p2]);
  const lines = csv.split('\n');
  expect(lines).toHaveLength(3);
  expect(lines[1]).toContain('pay_001');
  expect(lines[2]).toContain('pay_002');
});

test('exportPayouts skips payment with invalid PAN', () => {
  const invalid: Payment = { ...base, id: 'pay_bad', pan: '4111111111111112' }; // fails Luhn
  const csv = exportPayouts([invalid, base]);
  const lines = csv.split('\n');
  // only the header + one valid row (base), the invalid PAN row is excluded
  expect(lines).toHaveLength(2);
  expect(lines[1]).toContain('pay_001');
  expect(csv).not.toContain('pay_bad');
});

// --- log parameter tests ---

test('exportPayouts calls log once per exported payment', () => {
  const lines: string[] = [];
  const p2: Payment = { ...base, id: 'pay_002', merchantId: 'm_demo_002', status: 'settled' };
  exportPayouts([base, p2], (line) => lines.push(line));
  expect(lines).toHaveLength(2);
});

test('exportPayouts log line contains masked PAN', () => {
  const lines: string[] = [];
  exportPayouts([base], (line) => lines.push(line));
  expect(lines[0]).toContain('411111******1111');
});

test('exportPayouts log line never contains full PAN', () => {
  const lines: string[] = [];
  exportPayouts([base], (line) => lines.push(line));
  for (const line of lines) {
    expect(line).not.toContain('4111111111111111');
  }
});

test('exportPayouts log line format is correct', () => {
  const lines: string[] = [];
  exportPayouts([base], (line) => lines.push(line));
  expect(lines[0]).toBe('exported pay_001 411111******1111 EUR 10.00 EUR');
});

test('exportPayouts works without log parameter', () => {
  // no third argument — existing callers are unaffected
  const csv = exportPayouts([base]);
  expect(csv).toContain('pay_001');
});

test('exportPayouts does not log skipped (invalid PAN) payments', () => {
  const lines: string[] = [];
  const invalid: Payment = { ...base, id: 'pay_bad', pan: '4111111111111112' };
  exportPayouts([invalid, base], (line) => lines.push(line));
  expect(lines).toHaveLength(1);
  expect(lines[0]).toContain('pay_001');
});
