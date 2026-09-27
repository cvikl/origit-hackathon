import { processPayment } from 'fast-pay-utils';
import { Payment } from './types';
import { maskPan, formatAmount, validatePan } from './payment-utils';

/**
 * Export a list of payments as CSV.
 * Each payment is run through processPayment() before being serialised.
 * Columns: id,merchantId,amount,currency,maskedPan,status
 */
export function exportPayouts(
  payments: Payment[],
  log?: (line: string) => void,
): string {
  const header = 'id,merchantId,amount,currency,maskedPan,status';
  const rows = payments.filter((p) => validatePan(p.pan)).map((p) => {
    const processed = processPayment(p) as Payment;
    const masked = maskPan(processed.pan);
    const amount = formatAmount(processed.amountMinor, processed.currency);
    if (log) {
      log(`exported ${processed.id} ${masked} ${amount} ${processed.currency}`);
    }
    return [
      processed.id,
      processed.merchantId,
      amount,
      processed.currency,
      masked,
      processed.status,
    ].join(',');
  });
  return [header, ...rows].join('\n');
}

/**
 * Schedule a recurring export.
 * Every `intervalMs` milliseconds the `sink` function is called with the
 * CSV produced by exportPayouts for the given payments list.
 * Returns a cleanup function that cancels the interval.
 */
export function scheduleExport(
  intervalMs: number,
  payments: Payment[],
  sink: (csv: string) => void,
  log?: (line: string) => void,
): () => void {
  const id = setInterval(() => {
    sink(exportPayouts(payments, log));
  }, intervalMs);
  return () => clearInterval(id);
}
