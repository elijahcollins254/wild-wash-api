# BNPL Payment System - Updated Implementation

## Overview
The BNPL (Buy Now, Pay Later) payment system now has improved balance tracking with support for partial payments and proper M-Pesa transaction status synchronization.

## Key Changes

### 1. **Payment Amount Flexibility**
- Users can now pay partial amounts or the full balance
- The `pay_balance` endpoint accepts an optional `amount` parameter
- If no amount is specified, the full balance is used

### 2. **Proper Balance Reduction**
- Balance is reduced by the **payment amount**, not cleared entirely
- Supports multiple partial payments
- Ensures balance never goes negative

### 3. **M-Pesa Status Synchronization**
- Added `_query_transaction_status()` method for synchronous status checking
- Backend polls M-Pesa directly instead of waiting only for async callbacks
- Result codes handled: `0` = Success, `1` = Processing, other = Failed

### 4. **Dedicated Payment Status Endpoint**
- New `/payments/bnpl/check_pending_payment/` GET endpoint
- Returns explicit payment status with balance updates
- Returns payment amount for tracking partial payments

## API Endpoints

### Get BNPL Status
```
GET /api/payments/bnpl/status/
```
**Description**: Get current BNPL enrollment and balance status
**Query pending payments**: Automatically checks M-Pesa for pending payments

**Response**:
```json
{
  "is_enrolled": true,
  "credit_limit": 5000.00,
  "current_balance": 2500.00,
  "is_active": true,
  "phone_number": "254712345678"
}
```

---

### Check Pending Payment
```
GET /api/payments/bnpl/check_pending_payment/
```
**Description**: Check status of pending BNPL balance payment with real-time M-Pesa query

**Response (Success)**:
```json
{
  "has_pending_payment": false,
  "payment_status": "success",
  "message": "Payment completed successfully",
  "current_balance": 1250.00,
  "credit_limit": 5000.00,
  "payment_amount": 1250.00
}
```

**Response (Processing)**:
```json
{
  "has_pending_payment": true,
  "payment_status": "processing",
  "message": "Payment is still being processed. Please wait.",
  "current_balance": 2500.00
}
```

**Response (Failed)**:
```json
{
  "has_pending_payment": false,
  "payment_status": "failed",
  "message": "Payment failed. Please try again.",
  "current_balance": 2500.00,
  "credit_limit": 5000.00
}
```

---

### Initiate Balance Payment
```
POST /api/payments/bnpl/pay_balance/
```
**Description**: Initiate M-Pesa STK Push payment for BNPL balance

**Request (Full Balance)**:
```json
{
  "phone_number": "254712345678"
}
```

**Request (Custom Amount)**:
```json
{
  "phone_number": "254712345678",
  "amount": 1500.00
}
```

**Response**:
```json
{
  "status": "success",
  "message": "STK push sent to your phone to pay BNPL balance",
  "checkout_request_id": "ws_CO_DMZ_123456789_2026-05-03T10:00:00Z",
  "amount": 1500.00,
  "balance": 2500.00
}
```

**Error Cases**:
- Amount exceeds balance: `400 Bad Request`
- Invalid amount: `400 Bad Request`
- No outstanding balance: `400 Bad Request`
- Phone number required: `400 Bad Request`

---

## Frontend Integration

### Payment Flow
1. User clicks "Pay Now" button
2. Input field appears for custom amount (optional)
3. User confirms payment
4. Frontend polls `/check_pending_payment/` every 2-3 seconds
5. Upon success, balance is updated and modal shows confirmation
6. Manual refresh button available during pending state

### State Management
```typescript
{
  paymentPending: boolean,      // Whether payment is processing
  showPaymentInput: boolean,    // Show/hide custom amount input
  paymentAmount: string,        // User-entered custom amount
}
```

---

## Technical Details

### Balance Reduction Logic
```python
# When payment succeeds:
bnpl_user.current_balance -= Decimal(str(payment.amount))
bnpl_user.current_balance = max(bnpl_user.current_balance, Decimal('0'))
```

### M-Pesa Query Result Codes
- `0` or `'0'`: Transaction successful
- `1` or `'1'`: Transaction still processing
- Other codes: Transaction failed

### Callback Handler
The async callback handler also updates balance when it arrives (as fallback):
- Marks payment as success
- Reduces balance by payment amount
- Works independently of sync polling

---

## Testing

### Run Test Script
```bash
cd wild-wash-api
python scripts/test_bnpl_payment.py
```

### Test Scenarios
1. Get BNPL status
2. Check pending payments (when none exist)
3. Initiate full balance payment
4. Initiate custom amount payment
5. Invalid payment scenarios:
   - Amount exceeding balance
   - Zero amount
   - Negative amount

---

## Debugging

### Enable Logging
Check Django logs for detailed M-Pesa query responses:
```python
logger.info(f"M-Pesa query response: ResultCode={result_code}")
logger.info(f"Full response: {result}")
```

### Payment Records
Query Payment model for transaction history:
```python
from payments.models import Payment

# Get all BNPL payments for a user
payments = Payment.objects.filter(
    user=user,
    raw_payload__is_bnpl_balance_payment=True
).order_by('-created_at')
```

### Check Payment Status
```python
# Get latest pending BNPL payment
pending = Payment.objects.filter(
    user=user,
    status='initiated',
    raw_payload__is_bnpl_balance_payment=True
).order_by('-created_at').first()

if pending:
    print(f"Provider Reference: {pending.provider_reference}")
    print(f"Amount: {pending.amount}")
    print(f"Status: {pending.status}")
```

---

## Troubleshooting

### Payment not confirming
1. Check M-Pesa has actually processed the transaction (check phone)
2. Look at Payment record status in admin
3. Check logs for M-Pesa query errors
4. Try manual refresh button

### Balance not updating
1. Verify payment status is "success" in Payment model
2. Check BNPLUser.current_balance wasn't corrupted
3. Run `/check_pending_payment/` to force re-query M-Pesa

### Custom amount issues
1. Ensure amount is numeric and positive
2. Amount cannot exceed current_balance
3. Check frontend validation is working

---

## Future Improvements
- [ ] Schedule retry for failed M-Pesa queries
- [ ] Email notifications for payment success/failure
- [ ] Payment plan customization
- [ ] Transaction history export
- [ ] Admin analytics dashboard
