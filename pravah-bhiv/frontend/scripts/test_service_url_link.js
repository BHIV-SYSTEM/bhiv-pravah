/**
 * Unit Test for ServiceUrlLink sanitizeAndValidateUrl logic
 */
const assert = require('assert');

function sanitizeAndValidateUrl(rawUrl) {
  if (!rawUrl || typeof rawUrl !== 'string') {
    return { isValid: false, href: '', displayUrl: 'N/A' };
  }

  const trimmed = rawUrl.trim();
  if (
    !trimmed ||
    trimmed === '-' ||
    trimmed.toLowerCase() === 'n/a' ||
    trimmed.toLowerCase() === 'null' ||
    trimmed.toLowerCase() === 'unknown' ||
    trimmed.toLowerCase() === 'internal service'
  ) {
    return { isValid: false, href: '', displayUrl: trimmed || 'N/A' };
  }

  // Reject malicious schemes
  if (trimmed.toLowerCase().startsWith('javascript:') || trimmed.toLowerCase().startsWith('data:')) {
    return { isValid: false, href: '', displayUrl: trimmed };
  }

  try {
    let toParse = trimmed;
    if (!toParse.startsWith('http://') && !toParse.startsWith('https://')) {
      toParse = `http://${toParse}`;
    }

    const parsed = new URL(toParse);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return { isValid: false, href: '', displayUrl: trimmed };
    }

    // Strip userinfo credentials (user:password)
    parsed.username = '';
    parsed.password = '';

    // Redact sensitive query parameters if present
    const sensitiveKeys = ['token', 'secret', 'key', 'auth', 'apikey', 'api_key', 'access_token', 'jwt', 'password'];
    for (const key of Array.from(parsed.searchParams.keys())) {
      if (sensitiveKeys.includes(key.toLowerCase())) {
        parsed.searchParams.set(key, 'REDACTED');
      }
    }

    return {
      isValid: true,
      href: parsed.toString(),
      displayUrl: trimmed,
    };
  } catch {
    return { isValid: false, href: '', displayUrl: trimmed };
  }
}

console.log('Running ServiceUrlLink Unit Tests...');

// 1. Standard valid HTTP/HTTPS URLs
const res1 = sanitizeAndValidateUrl('https://gurukul-up9j.onrender.com');
assert.strictEqual(res1.isValid, true);
assert.strictEqual(res1.href, 'https://gurukul-up9j.onrender.com/');
console.log('✓ Valid HTTPS URL passed');

// 2. URL without protocol prepends http://
const res2 = sanitizeAndValidateUrl('localhost:8000/api/health');
assert.strictEqual(res2.isValid, true);
assert.strictEqual(res2.href, 'http://localhost:8000/api/health');
console.log('✓ URL without protocol prepends http passed');

// 3. User credentials stripped
const res3 = sanitizeAndValidateUrl('http://admin:secretpass@localhost:8080/dashboard');
assert.strictEqual(res3.isValid, true);
assert.strictEqual(res3.href.includes('secretpass'), false);
assert.strictEqual(res3.href, 'http://localhost:8080/dashboard');
console.log('✓ Stripped credentials passed');

// 4. Sensitive tokens redacted
const res4 = sanitizeAndValidateUrl('https://api.example.com/data?token=xyz123&user=john');
assert.strictEqual(res4.isValid, true);
assert.strictEqual(res4.href.includes('xyz123'), false);
assert.strictEqual(res4.href.includes('REDACTED'), true);
console.log('✓ Sensitive token redaction passed');

// 5. Malicious schemes rejected
const res5 = sanitizeAndValidateUrl('javascript:alert(1)');
assert.strictEqual(res5.isValid, false);
console.log('✓ Malicious scheme rejection passed');

// 6. Placeholders rejected
assert.strictEqual(sanitizeAndValidateUrl('N/A').isValid, false);
assert.strictEqual(sanitizeAndValidateUrl('-').isValid, false);
assert.strictEqual(sanitizeAndValidateUrl('unknown').isValid, false);
assert.strictEqual(sanitizeAndValidateUrl('Internal Service').isValid, false);
assert.strictEqual(sanitizeAndValidateUrl(null).isValid, false);
console.log('✓ Placeholder handling passed');

console.log('\nAll 6 unit test assertions passed successfully!');
