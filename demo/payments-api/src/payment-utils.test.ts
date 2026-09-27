import { formatAmount, maskPan, validatePan } from './payment-utils';

describe('formatAmount', () => {
  test('formats minor units as decimal with currency prefix', () => {
    expect(formatAmount(1099, 'EUR')).toBe('EUR 10.99');
  });

  test('formats whole amounts with two decimal places', () => {
    expect(formatAmount(1000, 'USD')).toBe('USD 10.00');
  });

  test('formats zero', () => {
    expect(formatAmount(0, 'GBP')).toBe('GBP 0.00');
  });
});

describe('maskPan', () => {
  test('keeps first 6 and last 4, masks the rest', () => {
    expect(maskPan('4111111111111111')).toBe('411111******1111');
  });

  test('works with different card numbers', () => {
    expect(maskPan('5500005555555559')).toBe('550000******5559');
  });
});

describe('validatePan', () => {
  test('returns true for a valid Luhn PAN', () => {
    expect(validatePan('4111111111111111')).toBe(true);
  });

  test('returns true for another valid PAN', () => {
    expect(validatePan('5500005555555559')).toBe(true);
  });

  test('returns false for an invalid PAN', () => {
    expect(validatePan('1234567890123456')).toBe(false);
  });

  test('returns false for non-digit input', () => {
    expect(validatePan('4111abc111111111')).toBe(false);
  });
});
