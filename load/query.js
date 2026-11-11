import http from 'k6/http';
import { SharedArray } from 'k6/data';
import { Trend, Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:18000';
const SCENARIO = __ENV.SCENARIO || 'baseline';
const RUN_TAG = __ENV.RUN_TAG || new Date().toISOString().slice(0, 10);
const OUT_DIR = __ENV.OUT_DIR || '/results'; // container mount; see Makefile

const QDIR = __ENV.QDIR || '/eval'; // container mount; see Makefile
const questions = new SharedArray('questions', () =>
  [open(QDIR + '/questions.jsonl'), open(QDIR + '/questions_manual.jsonl')]
    .flatMap((t) => t.split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l).question)));

const SCENARIOS = {
  smoke: { executor: 'shared-iterations', vus: 1, iterations: 3 },
  baseline: { executor: 'constant-vus', vus: 1, duration: '5m' },
  headline: { executor: 'constant-vus', vus: 4, duration: '10m' },
};
if (!SCENARIOS[SCENARIO]) throw new Error(`unknown SCENARIO=${SCENARIO}`);
const VUS = SCENARIOS[SCENARIO].vus; // not options.scenarios: CLI --vus/--iterations wipes it
export const options = {
  scenarios: { [SCENARIO]: SCENARIOS[SCENARIO] },
  thresholds: { http_req_failed: ['rate<0.05'] }, // reporting only: no abortOnFail
};

export function setup() {
  if (questions.length === 0) throw new Error(`no questions loaded from ${QDIR}`);
}

const latency = new Trend('latency_by_outcome', true);
const refusedRate = new Rate('refused');
const httpErrRate = new Rate('http_errors');

export default function () {
  const q = questions[(__ITER * VUS + __VU - 1) % questions.length];
  const res = http.post(`${BASE_URL}/query`, JSON.stringify({ question: q }), {
    headers: { 'content-type': 'application/json' },
    timeout: '120s',
  });
  const err = res.status >= 500 || res.status === 0;
  let refused = false;
  if (!err) { try { refused = res.json('refused') === true; } catch (e) { /* non-JSON body */ } }
  httpErrRate.add(err);
  refusedRate.add(refused);
  latency.add(res.timings.duration, { outcome: err ? 'error' : refused ? 'refused' : 'answered' });
}

export function handleSummary(data) {
  const m = data.metrics;
  const json = `${OUT_DIR}/load_${SCENARIO}_${RUN_TAG}.json`;
  if (!m.http_req_duration || !m.http_reqs) {
    const msg = `ERROR: zero HTTP requests (scenario=${SCENARIO} questions=${questions.length})\n`;
    return { [json]: JSON.stringify({ error: 'no http requests', data }, null, 2), stdout: msg };
  }
  const f = (x) => (x === undefined ? 'n/a' : x.toFixed(2));
  const text = [
    `scenario=${SCENARIO} tag=${RUN_TAG} questions=${questions.length}`,
    `p50=${f(m.http_req_duration.values.med)}ms p95=${f(m.http_req_duration.values['p(95)'])}ms`,
    `rps=${f(m.http_reqs.values.rate)} error_rate=${f((m.http_errors||{values:{}}).values.rate)} refused_rate=${f((m.refused||{values:{}}).values.rate)}`,
  ].join('\n') + '\n';
  return {
    [json]: JSON.stringify(data, null, 2),
    stdout: text,
  };
}
