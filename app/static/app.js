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

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function emptyBody(cols, text) {
  return `<tr class="empty"><td colspan="${cols}">${escapeHtml(text)}</td></tr>`;
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
      <td>${escapeHtml(fmtTime(session.started_at))}</td>
      <td>${escapeHtml(session.trainee_id || "-")}</td>
      <td>${escapeHtml(passedLabel(session.passed))}</td>
      <td>${escapeHtml(fmtSec(session.duration_sec))}</td>
      <td>${escapeHtml(stepLabel(session.reached_step || session.reached_phase || ""))}</td>
      <td>${escapeHtml(session.blocking_violations || 0)} / ${escapeHtml(session.warn_violations || 0)}</td>
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
  const drops = stats.dropSteps || [];
  expDrops.innerHTML = drops.length
    ? drops.map((item) =>
        `<tr><td>${escapeHtml(stepLabel(item.step))}</td><td>${item.count}</td></tr>`
      ).join("")
    : `<tr class="empty"><td colspan="2">없음</td></tr>`;
  expBody.innerHTML = "";
  const rows = (data.sessions || []).filter((session) => !isSmoke(session));
  if (rows.length === 0) {
    expBody.appendChild(emptyRow(6, "오늘 체험 세션이 없습니다."));
    return;
  }
  for (const session of rows) {
    expBody.appendChild(sessionRow(session, `
      <td>${escapeHtml(fmtTime(session.started_at))}</td>
      <td>${escapeHtml(session.device_id || "")}</td>
      <td>${escapeHtml(session.end_reason || session.status)}</td>
      <td>${escapeHtml(fmtSec(session.duration_sec))}</td>
      <td>${escapeHtml(stepLabel(session.reached_step || session.reached_phase || ""))}</td>
      <td><button type="button" data-open>상세</button></td>
    `));
  }
}

const SOP_GROUPS = [
  { name: "상황 인지", phase: "PrecursorCheck", steps: [["alarm_ack", "경보 인지"]] },
  { name: "CCTV·점검", phase: "AnomalyDetection", steps: [["cctv_reviewed", "CCTV·점검 이력"]] },
  { name: "PPE", phase: "PPE", steps: [
    ["ppe_suit", "방호복"],
    ["ppe_boots", "안전화"],
    ["ppe_respirator", "호흡기"],
    ["ppe_goggles", "보안경"],
    ["ppe_gloves", "장갑"],
    ["ppe_worn", "PPE 착용 완료"],
  ]},
  { name: "현장 확인", phase: "SiteCheck", steps: [
    ["site_entered", "현장 진입"],
    ["leak_gazed", "누출 응시"],
  ]},
  { name: "밸브 차단", phase: "Block", steps: [["valve_locked", "밸브 잠금"]] },
  { name: "봉쇄·중화", phase: "Contain", steps: [
    ["boom_deployed", "방수붐 전개"],
    ["neutralized", "중화"],
    ["pad_absorbed", "흡착 패드"],
  ]},
  { name: "폐기·제독", phase: "Collect", steps: [
    ["waste_packed", "폐기물 포장"],
    ["waste_binned", "폐기물 투입"],
    ["ventilation_on", "환기"],
    ["floor_cleaned", "바닥 정리"],
    ["decon_shower", "제독 샤워"],
    ["ppe_doff_gloves", "장갑 탈의"],
    ["ppe_doff_boots", "안전화 탈의"],
    ["ppe_doff_suit", "보호복 탈의"],
    ["ppe_doff_goggles", "보안경 탈의"],
    ["ppe_doff_respirator", "방독면 탈의"],
    ["ppe_doff_complete", "PPE 탈의 완료"],
    ["eyewash", "세안"],
  ]},
  { name: "종료", phase: "Done", steps: [["scenario_complete", "시나리오 종료"]] },
];

const SOP_STEPS = SOP_GROUPS.reduce((list, group) => list.concat(group.steps), []);

// 최종 보고는 예정. 체크리스트·이탈 다음 단계에 넣지 않는다.

function stepLabel(code) {
  if (!code) return "";
  if (code === "final_report") return "최종 보고(예정)";
  for (let i = 0; i < SOP_STEPS.length; i++) {
    if (SOP_STEPS[i][0] === code) return SOP_STEPS[i][1];
  }
  return code;
}

function phaseLabel(code) {
  const names = {
    None: "시작 전",
    PrecursorCheck: "상황 인지",
    AnomalyDetection: "CCTV·점검",
    PPE: "PPE",
    SiteCheck: "현장 확인",
    Block: "밸브 차단",
    Contain: "봉쇄·중화",
    Collect: "폐기·제독",
    Done: "종료",
  };
  return names[code] || code || "";
}

function typeLabel(code) {
  const names = {
    session_start: "세션 시작",
    session_end: "세션 종료",
    phase_enter: "phase 진입",
    phase_complete: "phase 완료",
    step_complete: "단계 완료",
    violation: "위반",
    heartbeat: "heartbeat",
  };
  return names[code] || code || "";
}

function completedSteps(session, result) {
  const set = {};
  const fromResult = result.stepsCompleted || [];
  for (let i = 0; i < fromResult.length; i++) {
    set[fromResult[i]] = true;
  }
  const events = session.events || [];
  for (let i = 0; i < events.length; i++) {
    if (events[i].type === "step_complete" && events[i].step) {
      set[events[i].step] = true;
    }
  }
  return set;
}

function skipStuck(code) {
  return code === "decon_shower" || code === "final_report";
}

function nextIncomplete(done) {
  for (let i = 0; i < SOP_STEPS.length; i++) {
    const code = SOP_STEPS[i][0];
    if (skipStuck(code)) continue;
    if (!done[code]) return SOP_STEPS[i];
  }
  return null;
}

function stuckMessage(session, done) {
  const reason = session.end_reason || session.status || "";
  if (reason === "completed" && done.scenario_complete) {
    return "끝까지 완료했습니다. 막힌 구간은 없습니다.";
  }
  const next = nextIncomplete(done);
  if (next) {
    const why =
      reason === "timeout" ? "시간 초과" :
      reason === "quit" ? "중도 종료" :
      reason === "completed" ? "종료됨" :
      reason || "진행 중";
    return why + " · 다음이 안 된 단계: " + next[1] + " (" + next[0] + ")";
  }
  return "도달 단계: " + stepLabel(session.reached_step || "");
}

function groupedRows(items, keyFn, render) {
  const groups = [];
  for (let i = 0; i < items.length; i++) {
    const key = keyFn(items[i]);
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.items.push(items[i]);
    else groups.push({ key, items: [items[i]] });
  }
  const rows = [];
  for (let g = 0; g < groups.length; g++) {
    const group = groups[g];
    for (let i = 0; i < group.items.length; i++) {
      rows.push(render(group.items[i], i === 0 ? group.items.length : 0, group.key));
    }
  }
  return rows.join("");
}

async function openDetail(sessionId) {
  currentDetailId = sessionId;
  const encodedSessionId = encodeURIComponent(sessionId);
  const session = await loadJson("/v1/sessions/" + encodedSessionId);
  panels.education.classList.remove("active");
  panels.experience.classList.remove("active");
  detail.classList.remove("hidden");
  detail.classList.add("active");
  document.getElementById("jsonl-link").href = "/v1/sessions/" + encodedSessionId + "/events.jsonl";
  const result = session.result && session.result.result ? session.result.result : session.result || {};
  const done = completedSteps(session, result);
  const next = nextIncomplete(done);
  const nextCode = next ? next[0] : null;
  document.getElementById("detail-stuck").textContent = stuckMessage(session, done);

  const summary = [
    ["모드", session.mode === "education" ? "교육" : session.mode === "experience" ? "체험" : session.mode || ""],
    ["교육생", session.trainee_id || "-"],
    ["이수", passedLabel(session.passed)],
    ["종료", session.end_reason || session.status || ""],
    ["소요", fmtSec(session.duration_sec) || "-"],
    ["도달", stepLabel(session.reached_step || session.reached_phase || "")],
  ];
  document.getElementById("detail-summary").innerHTML = summary.map((row, index) => {
    const group = index === 0
      ? `<td class="group" rowspan="${summary.length}">세션</td>`
      : "";
    return `<tr>${group}<td>${escapeHtml(row[0])}</td><td>${escapeHtml(row[1])}</td></tr>`;
  }).join("");

  const stepRows = [];
  SOP_GROUPS.forEach((group) => {
    group.steps.forEach((item, index) => {
      const code = item[0];
      const name = item[1];
      let cls = "step-todo";
      let status = "미완료";
      if (done[code]) {
        cls = "step-done";
        status = "완료";
      } else if (code === nextCode) {
        cls = "step-next";
        status = "다음";
      }
      const groupCell = index === 0
        ? `<td class="group" rowspan="${group.steps.length}">${escapeHtml(group.name)}</td>`
        : "";
      stepRows.push(
        `<tr class="${cls}">${groupCell}<td>${escapeHtml(name)}</td><td>${escapeHtml(code)}</td><td class="status">${status}</td></tr>`
      );
    });
  });
  document.getElementById("detail-steps").innerHTML = stepRows.join("");

  const phases = result.phaseDurationsSec || {};
  const phaseKeys = Object.keys(phases);
  document.getElementById("detail-phases").innerHTML = phaseKeys.length
    ? phaseKeys.map((key, index) => {
        const group = index === 0
          ? `<td class="group" rowspan="${phaseKeys.length}">소요</td>`
          : "";
        return `<tr>${group}<td>${escapeHtml(phaseLabel(key))}</td><td>${escapeHtml(fmtSec(phases[key]))}</td></tr>`;
      }).join("")
    : emptyBody(3, "없음");

  const violations = (session.events || []).filter((event) => event.type === "violation");
  document.getElementById("detail-violations").innerHTML = violations.length
    ? violations.map((event) =>
        `<tr><td>${escapeHtml(event.t)}</td><td>${escapeHtml(phaseLabel(event.phase))}</td><td>${escapeHtml(stepLabel(event.step))}</td><td>${escapeHtml(event.code)}</td><td>${escapeHtml(event.severity)}</td></tr>`
      ).join("")
    : emptyBody(5, "없음");

  const events = session.events || [];
  document.getElementById("detail-events").innerHTML = events.length
    ? groupedRows(
        events,
        (event) => event.phase || "",
        (event, rowspan, phase) => {
          const group = rowspan
            ? `<td class="group" rowspan="${rowspan}">${escapeHtml(phaseLabel(phase))}</td>`
            : "";
          return `<tr>${group}<td>${escapeHtml(event.t)}</td><td>${escapeHtml(typeLabel(event.type))}</td><td>${escapeHtml(stepLabel(event.step))}</td></tr>`;
        }
      )
    : emptyBody(4, "없음");
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
