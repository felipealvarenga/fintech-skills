// Stripe webhook (Express)
const stripe = require("stripe")(process.env.STRIPE_KEY);

app.post("/webhooks/stripe", express.json(), (req, res) => {
  const event = stripe.webhooks.constructEvent(JSON.stringify(req.body), req.headers["stripe-signature"], process.env.WHSEC);
  console.log("webhook", req.body);
  if (event.type === "payment_intent.succeeded") markPaid(event.data.object.metadata.orderId);
  res.sendStatus(200);
});
