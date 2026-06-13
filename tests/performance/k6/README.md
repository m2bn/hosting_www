# k6 Load Tests

This directory contains staging-only k6 scenarios for the SaaS hosting platform.

Run from this directory so `static-site.zip.base64` can be loaded:

```bash
cd tests/performance/k6
k6 run staging.load.js \
  -e LOAD_TEST_ENV=staging \
  -e API_BASE_URL=https://api.staging.example.com \
  -e DASHBOARD_BASE_URL=https://app.staging.example.com \
  -e LOAD_TEST_USER_EMAIL=owner.staging@example.com \
  -e LOAD_TEST_USER_PASSWORD="$LOAD_TEST_USER_PASSWORD" \
  -e LOAD_TEST_ORG_ID="$LOAD_TEST_ORG_ID" \
  -e LOAD_TEST_PROJECT_ID="$LOAD_TEST_PROJECT_ID" \
  -e LOAD_TEST_ENVIRONMENT_ID="$LOAD_TEST_ENVIRONMENT_ID" \
  -e LOAD_TEST_DEPLOYMENT_ID="$LOAD_TEST_DEPLOYMENT_ID"
```

The script refuses production-looking URLs. Do not override that guard for production.
