"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.processPayment = processPayment;
/** Validate and normalise a payment request. Pure; no I/O. */
function processPayment(details) {
    if (!details || typeof details !== 'object') throw new Error('processPayment: details required');
    if (typeof details.amountMinor !== 'number' || details.amountMinor <= 0) throw new Error('processPayment: amountMinor must be > 0');
    return { ...details, status: 'authorised', processedAt: new Date().toISOString() };
}
