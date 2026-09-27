import { Payment } from './types';

const store = new Map<string, Payment>();

export function create(payment: Payment): Payment {
  store.set(payment.id, payment);
  return payment;
}

export function get(id: string): Payment | undefined {
  return store.get(id);
}

export function list(): Payment[] {
  return Array.from(store.values());
}

/** Clear all records (used in tests). */
export function clear(): void {
  store.clear();
}
