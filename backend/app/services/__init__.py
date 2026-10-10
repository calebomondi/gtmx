"""Business logic and database access. Services take an AsyncSession and raise
the domain errors in services.errors; they never import FastAPI. Endpoints stay
thin: parse, authorize (api.deps), call a service, return a response model."""
