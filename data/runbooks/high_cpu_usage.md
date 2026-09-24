# High CPU Usage

## Symptoms

Common symptoms include:

- CPU utilization above 85 percent
- Increased response latency
- Request queue growth
- Slow background jobs
- Container CPU throttling

## Investigation

Review CPU metrics across every service instance.

Check whether the CPU increase started after:

- A deployment
- An increase in request volume
- A new background job
- A configuration change

Search logs for repeated processing, infinite loops, and expensive queries.

## Remediation

Possible actions include:

- Scale the service horizontally
- Roll back a faulty deployment
- Stop an expensive background job
- Optimize the affected operation

Scaling or rollback requires human approval.