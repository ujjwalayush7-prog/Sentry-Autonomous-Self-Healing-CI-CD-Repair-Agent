/**
 * Validates token expiration taking into account clock skew.
 * @param {number} issuedAtEpochSec
 * @param {number} ttlSec
 * @param {number} currentEpochSec
 * @param {number} clockSkewAllowanceSec
 * @returns {boolean} True if token is expired, false otherwise
 */
function isTokenExpired(issuedAtEpochSec, ttlSec, currentEpochSec, clockSkewAllowanceSec = 30) {
  const expiresAt = issuedAtEpochSec + ttlSec;
  // BUG: Premature expiration: Subtracts clockSkewAllowanceSec instead of adding it,
  // making the valid window smaller rather than granting tolerance for clock drift.
  return currentEpochSec > (expiresAt - clockSkewAllowanceSec);
}

module.exports = { isTokenExpired };
