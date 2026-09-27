export interface PaymentDetails { id: string; merchantId: string; amountMinor: number; currency: string; pan: string; }
export interface ProcessedPayment extends PaymentDetails { status: 'authorised'; processedAt: string; }
/** Validate and normalise a payment request. Pure; no I/O. */
export declare function processPayment(details: PaymentDetails): ProcessedPayment;
