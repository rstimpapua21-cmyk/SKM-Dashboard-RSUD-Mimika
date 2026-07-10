# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this repository, please **do not** open a public issue. Instead, report it privately to the repository maintainers so it can be addressed before public disclosure.

## Best Practices

- Never commit secrets, tokens, or credentials to the repository
- Use Subresource Integrity (SRI) for all CDN dependencies
- Apply Content Security Policy (CSP) headers/meta tags
- Sanitize all user-controlled data before rendering with innerHTML
- Avoid CORS wildcard (`Access-Control-Allow-Origin: *`) in production
- Only deploy necessary files to GitHub Pages (exclude server-side code)
