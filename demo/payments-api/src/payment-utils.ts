// Utility functions for payment processing: amount formatting, PAN masking, and Luhn validation.
/**
 * Format a minor-unit integer amount as a decimal string with currency code.
 * e.g. formatAmount(1099, 'EUR') -> 'EUR 10.99'
 */
export function formatAmount(minor: number, currency: string): string {
  const major = (minor / 100).toFixed(2);
  return `${currency} ${major}`;
}

/**
 * Mask a PAN: keep first 6 and last 4 digits, replace the rest with ******.
 * e.g. '4111111111111111' -> '411111******1111'
 */
export function maskPan(pan: string): string {
  return pan.replace(/^(\d{6})\d+(\d{4})$/, '$1******$2');
}

/**
 * Validate a PAN using the Luhn algorithm.
 * Returns true if the number passes the check.
 */
export function validatePan(pan: string): boolean {
  if (!/^\d+$/.test(pan)) return false;
  let sum = 0;
  let shouldDouble = false;
  for (let i = pan.length - 1; i >= 0; i--) {
    let digit = parseInt(pan[i], 10);
    if (shouldDouble) {
      digit *= 2;
      if (digit > 9) digit -= 9;
    }
    sum += digit;
    shouldDouble = !shouldDouble;
  }
  return sum % 10 === 0;
}
