import React from 'react';
import { ExternalLink } from 'lucide-react';

interface ServiceUrlLinkProps {
  url?: string | null;
  className?: string;
  truncateClass?: string;
  showIcon?: boolean;
  stopProp?: boolean;
}

export function sanitizeAndValidateUrl(rawUrl?: string | null): {
  isValid: boolean;
  href: string;
  displayUrl: string;
} {
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

export const ServiceUrlLink: React.FC<ServiceUrlLinkProps> = ({
  url,
  className = '',
  truncateClass = 'truncate max-w-[200px]',
  showIcon = true,
  stopProp = true,
}) => {
  const { isValid, href, displayUrl } = sanitizeAndValidateUrl(url);

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (stopProp) {
      e.stopPropagation();
    }
  };

  if (!isValid) {
    return (
      <span className={`text-muted-foreground ${truncateClass} ${className}`} title={displayUrl}>
        {displayUrl}
      </span>
    );
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={handleClick}
      title={`Open ${href} in a new tab`}
      className={`inline-flex items-center gap-1 text-primary hover:text-primary/80 hover:underline transition-colors font-mono select-all ${truncateClass} ${className}`}
    >
      <span className="truncate">{displayUrl}</span>
      {showIcon && <ExternalLink className="w-2.5 h-2.5 shrink-0 opacity-70" />}
    </a>
  );
};

export default ServiceUrlLink;
