# Application Memory Leak

## Symptoms

Common symptoms include:

- Memory usage continuously increasing
- Out-of-memory errors
- Container restarts
- Increased garbage-collection activity
- Service performance degrading over time

## Investigation

Review memory usage over time rather than using only the latest value.

Check application logs for:

- Out-of-memory errors
- Repeated container restarts
- Large object allocations
- Unreleased resources

Review recent deployments for changes involving caching, file processing, or large data objects.

## Remediation

Restarting an instance can temporarily restore service, but it does not fix the underlying leak.

A production restart or rollback requires human approval.

Create a follow-up engineering task to identify and fix the source of retained memory.