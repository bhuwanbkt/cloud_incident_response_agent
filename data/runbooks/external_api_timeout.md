# External API Timeout

## Symptoms

Common symptoms include:

- Upstream timeout errors
- Increased request latency
- Circuit breaker activation
- Failed requests to an external provider
- Retry volume increasing rapidly

## Investigation

Identify the affected external provider.

Check:

- Provider response time
- Application timeout configuration
- Retry count
- Circuit-breaker state
- Recent integration changes

Determine whether the failure is internal or caused by the external provider.

## Remediation

Possible actions include:

- Enable a safe fallback
- Reduce excessive retries
- Open the circuit breaker
- Contact the external provider
- Roll back a recent integration change

Do not repeatedly retry requests when the provider is unavailable.