# Security Fix: Checkout Price Manipulation Vulnerability

## Issue Summary
A critical security vulnerability was discovered in the checkout flow where users could manipulate the payment amount in the URL to pay less than the actual order requires.

### Vulnerability Details
**Type:** Price Manipulation / Payment Fraud  
**Severity:** CRITICAL 🔴  
**Affected Components:** 
- `/checkout` page (Frontend)
- `/api/payments/mpesa/stk-push/` endpoint (Backend)
- `/api/payments/bnpl/process/` endpoint (Backend)

### The Attack
1. User goes to checkout with a legitimate order: `/checkout?order_id=WW-00225&amount=5000`
2. User manipulates the URL: `/checkout?order_id=WW-00225&amount=1`
3. Frontend sends payment request with `amount: 1` to the backend
4. Backend accepts the 1 shilling payment without validating against the actual order price
5. User makes payment of 1 shilling via M-Pesa
6. Payment is recorded as successful since it matches the (fraudulent) amount sent to the API
7. Order is marked as paid with only 1 shilling received instead of the actual 5000 KES

## Root Cause
The backend payment endpoints were accepting the amount directly from the request payload without verifying that it matches the actual order price stored in the database.

### Vulnerable Code (BEFORE)
```python
# payments/views.py - MpesaSTKPushView.post()
def post(self, request):
    amount = request.data.get('amount')  # ❌ Trusts client-provided amount
    order_id = request.data.get('order_id')
    
    # ... no validation that amount matches order.price ...
    
    # Creates payment with unvalidated amount
    payment = Payment.objects.create(
        user=request.user,
        amount=amount,  # ❌ Could be anything
        ...
    )
```

## The Fix
Added server-side validation to ensure the payment amount matches the actual order price in the database.

### Fixed Code (AFTER)
```python
# payments/views.py - MpesaSTKPushView.post()
def post(self, request):
    amount_float = float(amount)
    amount = int(amount_float)
    
    # ✅ SECURITY: Validate amount against actual order price
    validation_error = self._validate_mpesa_order_amount(order_id, amount_float)
    if validation_error:
        return validation_error
    
    # ... proceeds only if amount matches order price ...
```

### Validation Method
Both M-Pesa and BNPL payment processors now include the same validation logic:

```python
def _validate_mpesa_order_amount(self, order_id, amount):
    """Validate that the provided amount matches the actual order price."""
    
    # Skip validation for game wallet top-ups
    if order_id is None or order_id == 'GAME_WALLET_TOPUP':
        return None
    
    # Fetch order from database by code
    try:
        order = Order.objects.get(code=order_id)
    except Order.DoesNotExist:
        return error_response('Order not found')
    
    # Get actual order price
    order_price = order.actual_price or order.price
    
    # Compare amounts (allow 0.01 tolerance for rounding)
    if abs(Decimal(str(order_price)) - Decimal(str(amount))) > Decimal('0.01'):
        # ❌ FRAUD DETECTED
        logger.warning(f"[SECURITY] FRAUD ALERT - Amount mismatch: {amount} vs {order_price}")
        return error_response('Payment amount does not match order total')
    
    # ✅ Validation passed
    return None
```

## Changes Made

### 1. Backend API Endpoints Fixed
- **`POST /api/payments/mpesa/stk-push/`** - Added amount validation before initiating M-Pesa STK Push
- **`POST /api/payments/bnpl/process/`** - Added amount validation before processing BNPL payment

### 2. Validation Logic
- **Location:** `wild-wash-api/payments/views.py`
- **Methods Added:**
  - `MpesaSTKPushView._validate_mpesa_order_amount(order_id, amount)`
  - `BNPLViewSet._validate_bnpl_order_amount(order_id, amount)`

### 3. Error Handling
When amount mismatch is detected:
```json
{
  "detail": "Payment amount does not match order total",
  "expected_amount": 5000,
  "provided_amount": 1,
  "order_id": "WW-00225"
}
```

## Frontend Security Notes

### Current State (No Changes Required)
The frontend already has proper safeguards:
- Amount and Order ID fields are marked as `readonly` and `disabled`
- Values are set from URL params but cannot be edited by users
- However, the URL params could still be manipulated, which is why backend validation is critical

```tsx
// app/checkout/checkout-form.tsx
<input
  type="number"
  name="amount"
  value={formData.amount}
  disabled={true}        // ✅ Prevents direct editing
  readOnly={true}        // ✅ Makes field read-only
  className="... opacity-75 ..."
/>
```

## How the Fix Prevents the Attack

### Before Fix
1. User modifies URL: `/checkout?order_id=WW-00225&amount=1`
2. Frontend shows amount=1 (but can't change it further due to readonly)
3. Submits to API with amount=1
4. **Backend accepts it** ❌ (vulnerable)
5. Payment of 1 shilling completes
6. Order marked as paid ❌ (fraud succeeded)

### After Fix
1. User modifies URL: `/checkout?order_id=WW-00225&amount=1`
2. Frontend shows amount=1
3. Submits to API with amount=1
4. **Backend validates**: Fetches order WW-00225 from database
5. **Backend checks**: 1 KES != 5000 KES (order.price)
6. **Backend rejects**: Returns HTTP 400 with error details
7. Payment fails ✅ (fraud prevented)

## Testing the Fix

### Test Case 1: Valid Payment
```bash
curl -X POST http://localhost:8000/api/payments/mpesa/stk-push/ \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "WW-00225",
    "amount": 5000,
    "phone": "254712345678"
  }'
```
**Expected Result:** ✅ Success - Amount matches order price

### Test Case 2: Fraudulent Payment (Underpayment)
```bash
curl -X POST http://localhost:8000/api/payments/mpesa/stk-push/ \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "WW-00225",
    "amount": 1,
    "phone": "254712345678"
  }'
```
**Expected Result:** ❌ HTTP 400 with "Payment amount does not match order total"

### Test Case 3: Game Wallet Top-up (No Order)
```bash
curl -X POST http://localhost:8000/api/payments/mpesa/stk-push/ \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": null,
    "amount": 1000,
    "phone": "254712345678"
  }'
```
**Expected Result:** ✅ Success - Game wallet top-ups don't require order validation

## Logging & Monitoring

All validation attempts are logged with security markers:
```
[SECURITY] FRAUD ALERT - Amount mismatch for order WW-00225: requested=1, actual=5000
[SECURITY] Order amount validated successfully for WW-00225: 5000 KES
[SECURITY] BNPL Amount mismatch for order WW-00225: requested=1, actual=5000
```

**Recommendation:** Monitor logs for `[SECURITY] FRAUD ALERT` messages and investigate potential fraud attempts.

## Database Impact
No database changes required. The fix leverages existing `Order.code`, `Order.price`, and `Order.actual_price` fields.

## Rollback Plan
If issues occur:
1. Comment out the validation calls:
   ```python
   # validation_error = self._validate_mpesa_order_amount(order_id, amount_float)
   # if validation_error:
   #     return validation_error
   ```
2. Redeploy
3. Fix any issues and re-enable

## Additional Security Recommendations

1. **Add audit logging** for all payment attempts with price mismatches
2. **Implement rate limiting** on payment endpoints to prevent brute force attempts
3. **Add IP-based fraud detection** to flag suspicious payment patterns
4. **Implement payment verification callback validation** to ensure M-Pesa callbacks match recorded amounts
5. **Add admin dashboard alerts** for failed payment attempts
6. **Consider 2FA** for large transactions

## Affected Files
- `wild-wash-api/payments/views.py` - Backend validation logic
- `wild-wash-api/orders/models.py` - No changes (uses existing Order model)
- `wildwash/app/checkout/checkout-form.tsx` - No changes (frontend already secure)

## Deployment Notes
- No database migrations required
- No configuration changes needed
- Backward compatible - game wallet top-ups continue to work
- Can be deployed immediately

## References
- CWE-863: Incorrect Authorization
- OWASP: A01:2021 – Broken Access Control
- Payment Card Industry Data Security Standard (PCI DSS)

---

**Fix Deployed:** February 22, 2026  
**Status:** ✅ RESOLVED
