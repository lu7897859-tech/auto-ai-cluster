# Payment Setup — One-Time Actions (15 minutes)

Do these ONCE. After that, everything runs automatically.

## 1. Stripe Account (for Western customers)
- Go to https://stripe.com → "Start now"
- Sign up with email: zslgh162122@126.com
- Dashboard → Products → "Add Product"
- Create "Form-B Architecture Paper" — $49 USD
- Create "Form-A Enterprise K8s Edition" — $6,800 USD / year
- For each product, generate a Payment Link
- Copy the Payment Link URLs

## 2. Update Checkout Page
- Edit payment/checkout.html
- Replace: `https://buy.stripe.com/placeholder-form-b`
- With your actual Stripe Payment Link URL

## 3. (Optional) Deploy Webhook
- auth-server.py on VPS (119.28.46.225)
- Stripe webhook → http://your-server:3001/webhook

## 4. What Happens Next
- Customer clicks "Buy Now" → Stripe checkout
- Pays via credit card / Apple Pay / Google Pay
- Money settles to your bank (3-5 business days)
- For Form-B PDF: upload PDF to Stripe for instant delivery
