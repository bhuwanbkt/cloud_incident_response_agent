# Database Connection Pool Exhaustion

## Symptoms

Common symptoms include:

- Increased request latency
- HTTP 500 responses
- Timeout waiting for database connections
- Database connection pool utilization above 90 percent
- Requests waiting longer than the configured connection timeout

## Investigation

Check application logs for messages such as:

- Database connection pool exhausted
- Timeout waiting for an available database connection
- Database connection acquisition exceeded the configured timeout

Review recent deployments for changes to:

- Database pool size
- Request timeout
- Application replica count
- Database connection configuration

Compare the incident start time with the deployment time.

## Remediation

If a recent deployment reduced the database pool size, restore the previous configuration or roll back the deployment.

Do not perform a production rollback without human approval.

After remediation, verify:

- Error rate returns below 1 percent
- P95 latency returns below 1000 milliseconds
- Connection pool utilization returns below 70 percent
- All service instances become healthy