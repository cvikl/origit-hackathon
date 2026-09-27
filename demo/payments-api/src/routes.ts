import { Router, Request, Response } from 'express';
import { randomUUID } from 'crypto';
import * as store from './store';
import { Payment } from './types';

const router = Router();

router.get('/health', (_req: Request, res: Response) => {
  res.json({ ok: true });
});

router.post('/payments', (req: Request, res: Response) => {
  const { merchantId, amountMinor, currency, pan } = req.body as Partial<Payment>;
  if (!merchantId || amountMinor === undefined || !currency || !pan) {
    res.status(400).json({ error: 'merchantId, amountMinor, currency and pan are required' });
    return;
  }
  const payment: Payment = {
    id: randomUUID(),
    merchantId,
    amountMinor,
    currency,
    pan,
    status: 'authorised',
    createdAt: new Date().toISOString(),
  };
  store.create(payment);
  res.status(201).json(payment);
});

router.get('/payments/:id', (req: Request, res: Response) => {
  const payment = store.get(req.params.id);
  if (!payment) {
    res.status(404).json({ error: 'not found' });
    return;
  }
  res.json(payment);
});

router.get('/payments', (_req: Request, res: Response) => {
  res.json(store.list());
});

export default router;
