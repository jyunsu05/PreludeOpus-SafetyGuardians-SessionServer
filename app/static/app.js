const eduBody = document.getElementById("edu-body");
const expBody = document.getElementById("exp-body");
const expStats = document.getElementById("exp-stats");
const expDrops = document.getElementById("exp-drops");
const detail = document.getElementById("detail");
const panels = {
  education: document.getElementById("education"),
  experience: document.getElementById("experience"),
};
let currentDetailId = null;

function fmtTime(value) {
  if (!value) return "";
  const raw = /Z$/i.test(value) ? value : value + "Z";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return value.replace("T", " ").replace("Z", "");
  }
  const pad = (n) => String(n).padStart(2, "0");
  return (
    date.getFullYear() +
    "-" +
    pad(date.getMonth() + 1) +
    "-" +
    pad(date.getDate()) +
    " " +
    pad(date.getHours()) +
    ":" +
    pad(date.getMinutes()) +
    ":" +
    pad(date.getSeconds())
  );
}

function isSmoke(session) {
  return session.session_id === "11111111-1111-1111-1111-111111111111";
}

function emptyRow(cols, text) {
  const tr = document.createElement("tr");
  tr.className = "empty";
  tr.innerHTML = `<td colspan="${cols}">${text}</td>`;
  return tr;
}

function fmtSec(value) {
  if (value == null || value === "") return "";
  return Number(value).toFixed(0) + "s";
}

function passedLabel(value) {
  if (value === 1 || value === true) return "이수";
  if (value === 0 || value === false) return "미이수";
  return "진행";
}

async function loadJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(url + " " + res.status);
  return res.json();
}

function sessionRow(session, extra) {
  const tr = document.createElement("tr");
  tr.innerHTML = extra;
  tr.querySelector("[data-open]").addEventListener("click", () => openDetail(session.session_id));
  return tr;
}

async function loadEducation() {
  const data = await loadJson("/v1/sessions?mode=education");
  const rows = (data.sessions || []).filter((session) => !isSmoke(session));
  eduBody.innerHTML = "";
  if (rows.length === 0) {
    eduBody.appendChild(emptyRow(7, "아직 세션이 없습니다. Unity에서 Play 하면 여기에 나타납니다."));
    return;
  }
  for (const session of rows) {
    eduBody.appendChild(sessionRow(session, `
      <td>${fmtTime(session.started_at)}</td>
      <td>${session.trainee_id || "-"}</td>
      <td>${passedLabel(session.passed)}</td>
      <td>${fmtSec(session.duration_sec)}</td>
      <td>${session.reached_step || session.reached_phase || ""}</td>
      <td>${session.blocking_violations || 0} / ${session.warn_violations || 0}</td>
      <td><button type="button" data-open>상세</button></td>
    `));
  }
}

async function loadExperience() {
  const today = new Date().toISOString().slice(0, 10);
  const stats = await loadJson("/v1/stats/daily?mode=experience&date=" + today);
  const data = await loadJson("/v1/sessions?mode=experience&date=" + today);
  document.getElementById("csv-link").href = "/v1/export/sessions.csv?mode=experience&date=" + today;
  expStats.innerHTML = `
    <div class="card"><span>시작</span><strong>${stats.started}</strong></div>
    <div class="card"><span>완료</span><strong>${stats.completed}</strong></div>
    <div class="card"><span>timeout</span><strong>${stats.timeout}</strong></div>
    <div class="card"><span>평균</span><strong>${fmtSec(stats.averageDurationSec)}</strong></div>
  `;
  expDrops.innerHTML = (stats.dropSteps || [])
    .map((item) => `<li>${item.step} (${item.count})</li>`)
    .join("") || "<li>없음</li>";
  expBody.innerHTML = "";
  const rows = (data.sessions || []).filter((session) => !isSmoke(session));
  if (rows.length === 0) {
    expBody.appendChild(emptyRow(6, "오늘 체험 세션이 없습니다."));
    return;
  }
  for (const session of rows) {
    expBody.appendChild(sessionRow(session, `
      <td>${fmtTime(session.started_at)}</td>
      <td>${session.device_id || ""}</td>
      <td>${session.end_reason || session.status}</td>
      <td>${fmtSec(session.duration_sec)}</td>
      <td>${session.reached_step || session.reached_phase || ""}</td>
      <td><button type="button" data-open>상세</button></td>
    `));
  }
}

async function openDetail(sessionId) {
  currentDetailId = sessionId;
  const session = await loadJson("/v1/sessions/" + sessionId);
  panels.education.classList.remove("active");
  panels.experience.classList.remove("active");
  detail.classList.remove("hidden");
  detail.classList.add("active");
  document.getElementById("detail-title").textContent = session.session_id;
  document.getElementById("jsonl-link").href = "/v1/sessions/" + sessionId + "/events.jsonl";
  const result = session.result && session.result.result ? session.result.result : session.result || {};
  document.getElementById("detail-summary").textContent = JSON.stringify(
    {
      mode: session.mode,
      trainee: session.trainee_id,
      passed: session.passed,
      reason: session.end_reason,
      durationSec: session.duration_sec,
      reached: session.reached_step,
    },
    null,
    2
  );
  const phases = (result.phaseDurationsSec) || {};
  document.getElementById("detail-phases").innerHTML = Object.keys(phases)
    .map((key) => `<li>${key}: ${fmtSec(phases[key])}</li>`)
    .join("") || "<li>없음</li>";
  const steps = result.stepsCompleted || [];
  document.getElementById("detail-steps").innerHTML = steps.map((step) => `<li>${step}</li>`).join("") || "<li>없음</li>";
  document.getElementById("detail-events").innerHTML = (session.events || [])
    .map((event) => {
      const bits = [event.type, event.phase, event.step, event.code].filter(Boolean).join(" / ");
      return `<li>t=${event.t} ${bits}</li>`;
    })
    .join("");
}

document.getElementById("back").addEventListener("click", () => {
  currentDetailId = null;
  detail.classList.add("hidden");
  detail.classList.remove("active");
  const current = document.querySelector("nav button.active").dataset.tab;
  panels[current].classList.add("active");
});

document.querySelectorAll("nav button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    currentDetailId = null;
    detail.classList.add("hidden");
    detail.classList.remove("active");
    Object.keys(panels).forEach((key) => panels[key].classList.toggle("active", key === button.dataset.tab));
    if (button.dataset.tab === "education") {
      document.getElementById("csv-link").href = "/v1/export/sessions.csv?mode=education";
      loadEducation();
    } else {
      loadExperience();
    }
  });
});

async function refreshVisible() {
  if (document.hidden) {
    return;
  }

  try {
    const onDetail = currentDetailId && !detail.classList.contains("hidden");
    if (onDetail) {
      await openDetail(currentDetailId);
    } else {
      const tabButton = document.querySelector("nav button.active");
      const tab = tabButton ? tabButton.dataset.tab : "education";
      if (tab === "experience") {
        await loadExperience();
      } else {
        await loadEducation();
      }
    }

    const stamp = document.getElementById("refresh-stamp");
    if (stamp) {
      stamp.textContent = "자동 새로고침 " + new Date().toLocaleTimeString();
    }
  } catch (err) {
    const stamp = document.getElementById("refresh-stamp");
    if (stamp) {
      stamp.textContent = "서버에 연결하지 못했습니다";
    }
  }
}

refreshVisible();
setInterval(refreshVisible, 10000);
document.addEventListener("visibilitychange", function () {
  if (!document.hidden) {
    refreshVisible();
  }
});
