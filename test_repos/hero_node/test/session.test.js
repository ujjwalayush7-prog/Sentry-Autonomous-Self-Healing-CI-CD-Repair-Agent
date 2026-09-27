const { test, describe } = require('node:test');
const assert = require('node:assert');
const { validateSession } = require('../src/session_manager');

describe('Session Manager Verification', () => {
  test('should validate active fresh session', () => {
    const session = {
      userId: 'usr_101',
      token: { issuedAt: 1000, ttl: 300 } // expires at 1300
    };
    const result = validateSession(session, 1050);
    assert.strictEqual(result.valid, true);
    assert.strictEqual(result.userId, 'usr_101');
  });

  test('should tolerate clock skew when token is near expiration boundary', () => {
    const session = {
      userId: 'usr_202',
      token: { issuedAt: 1000, ttl: 300 } // expires at 1300
    };
    // At timestamp 1315, token is 15s past expiration, but within 30s clock skew allowance
    const result = validateSession(session, 1315);
    assert.strictEqual(result.valid, true, 'Token within clock skew tolerance should be considered valid');
  });

  test('should reject genuinely expired token beyond clock skew', () => {
    const session = {
      userId: 'usr_303',
      token: { issuedAt: 1000, ttl: 300 } // expires at 1300 + 30 skew = 1330
    };
    const result = validateSession(session, 1400);
    assert.strictEqual(result.valid, false);
    assert.strictEqual(result.reason, 'SESSION_EXPIRED');
  });
});
