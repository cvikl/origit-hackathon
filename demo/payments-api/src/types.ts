export type PaymentStatus = 'authorised' | 'settled' | 'failed';

export interface Payment {
  id: string;
  merchantId: string;
  amountMinor: number;
  currency: string;
  pan: string;
  status: PaymentStatus;
  createdAt: string;
}
