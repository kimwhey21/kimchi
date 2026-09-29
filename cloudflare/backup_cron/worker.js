// 깃허브 예약 실행의 예비 장치 (2026-09-29). Cloudflare Workers의 예약(매분)으로 돈다.
//
// 깃허브는 예약 실행을 늦추거나 빼먹는다(평소 18~22분 지연, 2026-09-29에는 오전 10시 이후 반나절 통째로 빠졌다).
// - direct: 예약 작업 전부를 깃허브 예약을 기다리지 않고 정시에 직접 누른다(2026-09-29부터; 처음엔 종가 사진만).
//           누르기가 실패하면 운영 텔레그램으로 알린다. 깃허브 예약은 예비로 남고, 늦게 온 예약은 skip_guard.yml이 건너뛴다.
// - watch : 예정 시각(due) 뒤 확인 시각(check)에 "due 5분 전부터 실행이 하나라도 생겼나"를 묻고, 없으면 대신 누르고 알린다.
//           지금은 비어 있다(모두 direct) — 정시에 누르면 안 되는 작업이 생기면 여기에 둔다.
// 표는 jobs.json이고 scripts/deploy_backup_cron.py가 여기 __JOBS__ 자리에 넣어 올린다.
// 비밀값(GH_TOKEN·TELEGRAM_BOT_TOKEN·TELEGRAM_ADMIN_CHAT_ID)은 Worker 비밀로만 있다.

const JOBS = __JOBS__;
const REPO = "kimwhey21/kimchi";

const pad = (n) => String(n).padStart(2, "0");
const hm = (d) => `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;

export function dayOk(spec, dow) {
  return spec.split(",").some((part) => {
    const [a, b] = part.split("-").map(Number);
    return b === undefined ? dow === a : dow >= a && dow <= b;
  });
}

function at(now, hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), h, m));
}

async function gh(env, path, init = {}) {
  return fetch(`https://api.github.com/repos/${REPO}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${env.GH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "fermata-backup-cron",
    },
  });
}

async function telegram(env, text) {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_ADMIN_CHAT_ID) return;
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ chat_id: env.TELEGRAM_ADMIN_CHAT_ID, text, disable_web_page_preview: true }),
  });
}

async function dispatch(env, job) {
  if (env.DRY_RUN) return console.log(`[시험] 실행할 것: ${job.workflow} ${JSON.stringify(job.inputs || {})}`);
  const r = await gh(env, `/actions/workflows/${job.workflow}/dispatches`, {
    method: "POST",
    body: JSON.stringify({ ref: "main", inputs: job.inputs || {} }),
  });
  if (r.status !== 204) throw new Error(`${job.workflow} 실행 버튼 실패 (${r.status})`);
}

async function ranSince(env, job, since) {
  const created = encodeURIComponent(`>=${since.toISOString().slice(0, 19)}Z`);
  const r = await gh(env, `/actions/workflows/${job.workflow}/runs?created=${created}&per_page=5`);
  if (!r.ok) throw new Error(`${job.workflow} 실행 목록 조회 실패 (${r.status})`);
  return (await r.json()).total_count > 0;
}

export async function run(env, now) {
  const minute = hm(now);
  const dow = now.getUTCDay();
  const done = [];
  for (const job of JOBS.direct) {
    if (!dayOk(job.days, dow) || !job.utc.includes(minute)) continue;
    try {
      await dispatch(env, job);
      done.push(`direct ${job.workflow}`);
    } catch (e) {
      await telegram(env, `❌ 예비 예약: ${e.message}`);
    }
  }
  for (const job of JOBS.watch) {
    if (!dayOk(job.days, dow) || job.check !== minute) continue;
    try {
      const since = new Date(at(now, job.due).getTime() - 5 * 60 * 1000);
      if (await ranSince(env, job, since)) continue;
      await dispatch(env, job);
      done.push(`watch ${job.workflow}`);
      const label = job.inputs?.market ? `${job.workflow} (${job.inputs.market})` : job.workflow;
      await telegram(env, `⚠️ 깃허브 예약이 빠져 ${label}을(를) 대신 실행했습니다 (예정 ${job.due} UTC).`);
    } catch (e) {
      await telegram(env, `❌ 예비 예약: ${e.message}`);
    }
  }
  return done;
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(run(env, new Date(event.scheduledTime)));
  },
};
