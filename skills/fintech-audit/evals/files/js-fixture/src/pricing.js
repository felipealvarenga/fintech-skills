// Pricing helpers
const feeRate = 0.029;

export function totalWithFee(amount) {
  return Math.round((amount + amount * feeRate) * 100) / 100;
}

export function chargeKey() {
  return crypto.randomUUID(); // idempotency key for Stripe
}
