import crypto from "k6/crypto";
import encoding from "k6/encoding";
import exec from "k6/execution";
import http from "k6/http";
import { check, fail, group, sleep } from "k6";

const API_BASE_URL = (__ENV.API_BASE_URL || "https://api.staging.example.com").replace(/\/$/, "");
const DASHBOARD_BASE_URL = (__ENV.DASHBOARD_BASE_URL || "https://app.staging.example.com").replace(/\/$/, "");
const LOAD_TEST_ENV = __ENV.LOAD_TEST_ENV || "staging";
const LOGIN_EMAIL = __ENV.LOAD_TEST_USER_EMAIL || "owner.staging@example.com";
const LOGIN_PASSWORD = __ENV.LOAD_TEST_USER_PASSWORD || "";
const ORG_ID = __ENV.LOAD_TEST_ORG_ID || "";
const PROJECT_ID = __ENV.LOAD_TEST_PROJECT_ID || "";
const ENVIRONMENT_ID = __ENV.LOAD_TEST_ENVIRONMENT_ID || "";
const DEPLOYMENT_ID = __ENV.LOAD_TEST_DEPLOYMENT_ID || "";
const STRIPE_WEBHOOK_SECRET = __ENV.STRIPE_WEBHOOK_SECRET || "";
const STATIC_SITE_ZIP = encoding.b64decode(open("./static-site.zip.base64").trim(), "rawstd", "s");

export const options = {
  scenarios: {
    login: {
      executor: "constant-vus",
      exec: "loginScenario",
      vus: Number(__ENV.K6_LOGIN_VUS || 3),
      duration: __ENV.K6_LOGIN_DURATION || "1m",
    },
    projects_list: {
      executor: "constant-vus",
      exec: "projectsListScenario",
      vus: Number(__ENV.K6_PROJECTS_VUS || 3),
      duration: __ENV.K6_PROJECTS_DURATION || "1m",
    },
    static_upload: {
      executor: "shared-iterations",
      exec: "staticUploadScenario",
      vus: Number(__ENV.K6_UPLOAD_VUS || 1),
      iterations: Number(__ENV.K6_UPLOAD_ITERATIONS || 3),
      maxDuration: __ENV.K6_UPLOAD_MAX_DURATION || "3m",
    },
    deployment: {
      executor: "shared-iterations",
      exec: "deploymentScenario",
      vus: Number(__ENV.K6_DEPLOYMENT_VUS || 1),
      iterations: Number(__ENV.K6_DEPLOYMENT_ITERATIONS || 2),
      maxDuration: __ENV.K6_DEPLOYMENT_MAX_DURATION || "3m",
    },
    stripe_webhook: {
      executor: "constant-arrival-rate",
      exec: "stripeWebhookScenario",
      rate: Number(__ENV.K6_STRIPE_WEBHOOK_RATE || 2),
      timeUnit: "1s",
      duration: __ENV.K6_STRIPE_WEBHOOK_DURATION || "1m",
      preAllocatedVUs: Number(__ENV.K6_STRIPE_WEBHOOK_VUS || 4),
    },
    deployment_logs: {
      executor: "constant-vus",
      exec: "deploymentLogsScenario",
      vus: Number(__ENV.K6_LOGS_VUS || 2),
      duration: __ENV.K6_LOGS_DURATION || "1m",
    },
    dashboard: {
      executor: "constant-vus",
      exec: "dashboardScenario",
      vus: Number(__ENV.K6_DASHBOARD_VUS || 3),
      duration: __ENV.K6_DASHBOARD_DURATION || "1m",
    },
    api_rate_limit: {
      executor: "shared-iterations",
      exec: "apiRateLimitScenario",
      vus: Number(__ENV.K6_RATE_LIMIT_VUS || 1),
      iterations: Number(__ENV.K6_RATE_LIMIT_ITERATIONS || 1),
      maxDuration: __ENV.K6_RATE_LIMIT_MAX_DURATION || "1m",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    "http_req_duration{scenario:login}": ["p(95)<750", "p(99)<1500"],
    "http_req_duration{scenario:projects_list}": ["p(95)<800"],
    "http_req_duration{scenario:static_upload}": ["p(95)<5000"],
    "http_req_duration{scenario:deployment}": ["p(95)<8000"],
    "http_req_duration{scenario:stripe_webhook}": ["p(95)<1000"],
    "http_req_duration{scenario:deployment_logs}": ["p(95)<1000"],
    "http_req_duration{scenario:dashboard}": ["p(95)<1200"],
    "checks{type:rate_limit}": ["rate>0.95"],
  },
};

export function setup() {
  assertStagingOnly();
  return {};
}

export function loginScenario() {
  group("login", () => {
    const session = login();
    check(session, {
      "login succeeded": (value) => value.authenticated,
    });
  });
  sleep(1);
}

export function projectsListScenario() {
  group("project list", () => {
    const session = login();
    if (!requireIds("projects_list", ORG_ID)) return;
    const response = http.get(`${API_BASE_URL}/api/organizations/${ORG_ID}/projects/`, {
      headers: csrfHeaders(session),
      tags: { scenario: "projects_list" },
    });
    check(response, {
      "project list returned 200": (r) => r.status === 200,
      "project list has results": (r) => String(r.body).includes("results"),
    });
  });
  sleep(1);
}

export function staticUploadScenario() {
  group("static site upload", () => {
    const session = login();
    if (!requireIds("static_upload", ORG_ID, PROJECT_ID, ENVIRONMENT_ID)) return;
    const response = postStaticDeployment(session, "static_upload");
    check(response, {
      "static upload accepted": (r) => [200, 201, 202].includes(r.status),
    });
  });
  sleep(1);
}

export function deploymentScenario() {
  group("deployment", () => {
    const session = login();
    if (!requireIds("deployment", ORG_ID, PROJECT_ID, ENVIRONMENT_ID)) return;
    const response = postStaticDeployment(session, "deployment");
    check(response, {
      "deployment accepted": (r) => [200, 201, 202].includes(r.status),
    });
  });
  sleep(1);
}

export function stripeWebhookScenario() {
  group("stripe webhook", () => {
    const eventId = `evt_k6_${Date.now()}_${exec.vu.idInTest}_${exec.scenario.iterationInTest}`;
    const payload = JSON.stringify({
      id: eventId,
      type: "invoice.payment_failed",
      data: {
        object: {
          id: `in_k6_${eventId}`,
          customer: __ENV.LOAD_TEST_STRIPE_CUSTOMER_ID || "cus_staging_seed",
          subscription: __ENV.LOAD_TEST_STRIPE_SUBSCRIPTION_ID || "sub_staging_seed",
          amount_due: 2500,
          amount_paid: 0,
          currency: "usd",
          metadata: { organization_public_id: ORG_ID },
          created: Math.floor(Date.now() / 1000),
          status_transitions: {},
        },
      },
    });
    const headers = { "Content-Type": "application/json" };
    if (STRIPE_WEBHOOK_SECRET) {
      headers["Stripe-Signature"] = stripeSignature(payload, STRIPE_WEBHOOK_SECRET);
    } else {
      headers["Stripe-Signature"] = "load-test-invalid-signature";
    }
    const response = http.post(`${API_BASE_URL}/api/billing/stripe/webhook/`, payload, {
      headers,
      tags: { scenario: "stripe_webhook" },
    });
    check(response, {
      "stripe webhook handled": (r) => (STRIPE_WEBHOOK_SECRET ? r.status === 200 : r.status === 400),
    });
  });
  sleep(1);
}

export function deploymentLogsScenario() {
  group("deployment logs", () => {
    const session = login();
    if (!requireIds("deployment_logs", ORG_ID, PROJECT_ID, ENVIRONMENT_ID, DEPLOYMENT_ID)) return;
    const response = http.get(
      `${API_BASE_URL}/api/organizations/${ORG_ID}/projects/${PROJECT_ID}/environments/${ENVIRONMENT_ID}/deployments/container/${DEPLOYMENT_ID}/logs/`,
      { headers: csrfHeaders(session), tags: { scenario: "deployment_logs" } },
    );
    check(response, {
      "deployment logs returned 200": (r) => r.status === 200,
      "deployment logs have results": (r) => String(r.body).includes("results"),
    });
  });
  sleep(1);
}

export function dashboardScenario() {
  group("dashboard", () => {
    const response = http.get(DASHBOARD_BASE_URL, { tags: { scenario: "dashboard" } });
    check(response, {
      "dashboard returned success": (r) => r.status >= 200 && r.status < 400,
      "dashboard is not blank": (r) => String(r.body).length > 500,
    });
  });
  sleep(1);
}

export function apiRateLimitScenario() {
  group("api rate limit", () => {
    const csrf = getCsrf();
    let sawRateLimit = false;
    for (let attempt = 0; attempt < Number(__ENV.K6_RATE_LIMIT_ATTEMPTS || 8); attempt += 1) {
      const response = http.post(
        `${API_BASE_URL}/api/auth/login/`,
        JSON.stringify({ email: `rate-limit-${Date.now()}@example.test`, password: "wrong-password" }),
        {
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf.token },
          tags: { scenario: "api_rate_limit", type: "rate_limit" },
        },
      );
      sawRateLimit = sawRateLimit || response.status === 429;
      if (sawRateLimit) break;
    }
    check(sawRateLimit, {
      "rate limit eventually returned 429": (value) => value === true,
    }, { type: "rate_limit" });
  });
}

function assertStagingOnly() {
  const joined = `${API_BASE_URL} ${DASHBOARD_BASE_URL}`.toLowerCase();
  if (LOAD_TEST_ENV !== "staging" && !joined.includes("localhost") && !joined.includes("127.0.0.1")) {
    fail("Load tests are allowed only with LOAD_TEST_ENV=staging or local URLs.");
  }
  if (joined.includes("production") || joined.includes("prod.") || joined.includes("api.example.com ") || joined.includes("app.example.com")) {
    fail("Refusing to run load tests against a production-looking URL.");
  }
}

function getCsrf() {
  const response = http.get(`${API_BASE_URL}/api/auth/csrf/`, { tags: { scenario: "csrf" } });
  const token = response.cookies.csrftoken && response.cookies.csrftoken[0] && response.cookies.csrftoken[0].value;
  return { token, cookies: response.cookies };
}

function login() {
  if (!LOGIN_PASSWORD) {
    fail("LOAD_TEST_USER_PASSWORD is required for authenticated load test scenarios.");
  }
  const csrf = getCsrf();
  const response = http.post(
    `${API_BASE_URL}/api/auth/login/`,
    JSON.stringify({ email: LOGIN_EMAIL, password: LOGIN_PASSWORD }),
    {
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf.token },
      tags: { scenario: "login" },
    },
  );
  return {
    authenticated: response.status === 200 || response.status === 204,
    csrfToken: csrf.token,
  };
}

function csrfHeaders(session) {
  return {
    "X-CSRFToken": session.csrfToken,
  };
}

function postStaticDeployment(session, scenario) {
  const payload = {
    file: http.file(STATIC_SITE_ZIP, `k6-${Date.now()}.zip`, "application/zip"),
  };
  return http.post(
    `${API_BASE_URL}/api/organizations/${ORG_ID}/projects/${PROJECT_ID}/environments/${ENVIRONMENT_ID}/deployments/static/`,
    payload,
    {
      headers: csrfHeaders(session),
      tags: { scenario },
    },
  );
}

function stripeSignature(payload, secret) {
  const timestamp = Math.floor(Date.now() / 1000);
  const signedPayload = `${timestamp}.${payload}`;
  const signature = crypto.hmac("sha256", secret.replace(/^whsec_/, ""), signedPayload, "hex");
  return `t=${timestamp},v1=${signature}`;
}

function requireIds(scenario, ...values) {
  const ok = values.every((value) => Boolean(value));
  if (!ok) {
    console.warn(`Skipping ${scenario}: required staging resource IDs are missing.`);
  }
  return ok;
}
