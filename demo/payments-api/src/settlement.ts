import { Payment } from './types';

const BACKOFF_MS = [10, 20, 40];
const MAX_ATTEMPTS = 3;

export function defaultDelay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function settle(
  payment: Payment,
  send: (p: Payment) => Promise<void>,
  delay: (ms: number) => Promise<void> = defaultDelay,
): Promise<Payment> {
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    try {
      await send(payment);
      return { ...payment, status: 'settled' };
    } catch {
      if (attempt < MAX_ATTEMPTS - 1) {
        await delay(BACKOFF_MS[attempt]);
      }
    }
  }
  return { ...payment, status: 'failed' };
}
