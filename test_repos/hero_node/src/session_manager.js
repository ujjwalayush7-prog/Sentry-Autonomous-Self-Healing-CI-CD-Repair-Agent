const { isTokenExpired } = require('./token_validator');

/**
 * Validates a session payload against expiration rules.
 */
function validateSession(session, nowSec) {
  if (!session || !session.token) {
    throw new Error('Invalid session payload: token missing');
  }

  const expired = isTokenExpired(
    session.token.issuedAt,
    session.token.ttl,
    nowSec,
    30 // 30-second clock skew tolerance
  );

  if (expired) {
    return { valid: false, reason: 'SESSION_EXPIRED' };
  }

  return { valid: true, userId: session.userId };
}

module.exports = { validateSession };
