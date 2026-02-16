const STORAGE_KEY = "broadListeningOpenSourceDemoStateV2";
const RESET_MS = 60 * 60 * 1000;
const DIRECTOR_1 = "Director 1";
const DIRECTOR_2 = "Director 2";
const USER_VOTER = DIRECTOR_2;

const MODULES = [
  {
    id: "script-master",
    section: "Script / Research",
    title: "Master Script",
    stake: 15,
    deliverables: "Story architecture, scene map, argument spine, and narration beat outline."
  },
  {
    id: "research-anno",
    section: "Script / Research",
    title: "Anno-san Research",
    stake: 7,
    deliverables: "Outline document tracing facts, events, and idea lineage around Anno-san and Team Mirai."
  },
  {
    id: "research-digital-democracy",
    section: "Script / Research",
    title: "Wider Digital Democracy Research",
    stake: 6,
    deliverables: "Outline document tracing key actors, events, and conceptual lineage in digital democracy."
  },
  {
    id: "footage-pre-mirai",
    section: "Footage",
    title: "Anno-san Observational Footage - Pre-Team Mirai",
    stake: 6,
    deliverables: "Logged observational rushes from the period before Team Mirai formation."
  },
  {
    id: "footage-upper-house",
    section: "Footage",
    title: "Anno-san Observational Footage - Upper House Election",
    stake: 6,
    deliverables: "Logged observational rushes from upper house election period."
  },
  {
    id: "footage-lower-house",
    section: "Footage",
    title: "Anno-san Observational Footage - Lower House Election",
    stake: 6,
    deliverables: "Logged observational rushes from lower house election period."
  },
  {
    id: "footage-animation",
    section: "Footage",
    title: "Animation Sequences",
    stake: 6,
    deliverables: "Animation assets and rendered sequences supporting speculative future scenes."
  },
  {
    id: "footage-scripted-sequences",
    section: "Footage",
    title: "Scripted / Constructed Sequences",
    stake: 5,
    deliverables: "Shot list execution and media package for constructed dramatic sequences."
  },
  {
    id: "footage-archive-news",
    section: "Footage",
    title: "Archive / News Clips",
    stake: 3,
    deliverables: "Archive pull list, rights status notes, and edit-ready media ingest."
  },
  {
    id: "footage-wider-dd",
    section: "Footage",
    title: "Wider Digital Democracy Footage",
    stake: 4,
    deliverables: "Supporting footage package for broader global digital democracy context."
  },
  {
    id: "post-narration",
    section: "Post-production",
    title: "Narration",
    stake: 4,
    deliverables: "Narration draft, final script polish, and recorded voice files."
  },
  {
    id: "post-rough-cut",
    section: "Post-production",
    title: "Rough Cut",
    stake: 8,
    deliverables: "Structural assembly with scene order, timing draft, and notes log."
  },
  {
    id: "post-fine-cut",
    section: "Post-production",
    title: "Fine Cut",
    stake: 7,
    deliverables: "Picture lock candidate with pacing, transitions, and revisions addressed."
  },
  {
    id: "post-sound-mix",
    section: "Post-production",
    title: "Sound Design / Mix",
    stake: 4,
    deliverables: "Designed soundscape and final mix stems/master."
  },
  {
    id: "post-subs-captions",
    section: "Post-production",
    title: "Subtitles + Captions",
    stake: 2,
    deliverables: "Timed subtitles and captions package for release and accessibility."
  },
  {
    id: "post-colour",
    section: "Post-production",
    title: "Colour",
    stake: 3,
    deliverables: "Color grade pass, look consistency check, and final online conform."
  },
  {
    id: "dist-press-kit",
    section: "Distribution",
    title: "Press Kit",
    stake: 2,
    deliverables: "Synopsis, project statement, stills, credits list, and key metadata."
  },
  {
    id: "dist-trailer",
    section: "Distribution",
    title: "Trailer",
    stake: 3,
    deliverables: "Trailer cut and export package for web/festival distribution."
  },
  {
    id: "dist-cinema-deliverables",
    section: "Distribution",
    title: "Cinema Distribution Deliverables",
    stake: 3,
    deliverables: "Festival and cinema deliverables package (DCP/master files/QC docs)."
  }
];

const SECTION_ORDER = ["Script / Research", "Footage", "Post-production", "Distribution"];

function createSeedState(time = Date.now()) {
  return {
    seededAt: time,
    nextContributionId: 5,
    contributions: [
      {
        id: 1,
        moduleId: "research-digital-democracy",
        contributor: "Mina Sato",
        title: "Digital democracy lineage outline",
        summary: "Delivered a source-based outline of key facts, events, and concept lineage.",
        links: ["https://example.com/digital-democracy-lineage"],
        status: "approved",
        ballots: [
          { voter: DIRECTOR_1, vote: "yes", weight: 50 },
          { voter: DIRECTOR_2, vote: "yes", weight: 50 }
        ],
        createdAt: time - 3 * 24 * 60 * 60 * 1000
      },
      {
        id: 2,
        moduleId: "research-anno",
        contributor: "Riku Tanaka",
        title: "Anno-san timeline and event map",
        summary: "Delivered a structured chronology of speeches, campaign moments, and policy framing.",
        links: [],
        status: "approved",
        ballots: [
          { voter: DIRECTOR_1, vote: "yes", weight: 47 },
          { voter: DIRECTOR_2, vote: "yes", weight: 47 }
        ],
        createdAt: time - 2 * 24 * 60 * 60 * 1000
      },
      {
        id: 3,
        moduleId: "footage-upper-house",
        contributor: "Aiko Mori",
        title: "Upper house campaign observation package",
        summary: "Submitted a first observational assembly and logging notes for campaign moments.",
        links: ["https://example.com/upper-house-observational-cut"],
        status: "pending",
        ballots: [{ voter: "Riku Tanaka", vote: "yes", weight: 7 }],
        createdAt: time - 45 * 60 * 1000
      },
      {
        id: 4,
        moduleId: "post-narration",
        contributor: "Ken Ito",
        title: "Narration draft pass",
        summary: "Submitted a narration draft aligning documentary and speculative future sections.",
        links: [],
        status: "pending",
        ballots: [{ voter: "Mina Sato", vote: "no", weight: 6 }],
        createdAt: time - 15 * 60 * 1000
      }
    ]
  };
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return createSeedState();
    }
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      return createSeedState();
    }
    if (Date.now() - Number(parsed.seededAt) >= RESET_MS) {
      return createSeedState();
    }
    if (!Array.isArray(parsed.contributions)) {
      return createSeedState();
    }
    return parsed;
  } catch (_err) {
    return createSeedState();
  }
}

let state = loadState();
const expandedSections = new Set();

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function resetState() {
  state = createSeedState();
  saveState();
  renderAll("Demo state reset. A fresh 1-hour session has started.");
}

function formatPercent(value) {
  if (Number.isInteger(value)) return `${value}%`;
  return `${value.toFixed(2)}%`;
}

function sectionTotals() {
  return SECTION_ORDER.map((section) => {
    const total = MODULES.filter((m) => m.section === section).reduce((sum, m) => sum + m.stake, 0);
    return { section, total };
  });
}

function moduleById(moduleId) {
  return MODULES.find((m) => m.id === moduleId);
}

function ballotTotals(ballots = []) {
  return ballots.reduce(
    (acc, ballot) => {
      if (ballot.vote === "yes") acc.yes += Number(ballot.weight || 0);
      if (ballot.vote === "no") acc.no += Number(ballot.weight || 0);
      return acc;
    },
    { yes: 0, no: 0 }
  );
}

function applyVoteOutcome(contribution) {
  if (contribution.status !== "pending") return;
  const totals = ballotTotals(contribution.ballots || []);
  if (totals.yes > 50) {
    contribution.status = "approved";
  } else if (totals.no > 50) {
    contribution.status = "rejected";
  }
}

function normalizeContributions() {
  state.contributions.forEach((contribution) => {
    if (!Array.isArray(contribution.ballots)) {
      contribution.ballots = [];
      if (contribution.votes) {
        if (Number(contribution.votes.yes) > 0) {
          contribution.ballots.push({ voter: "Legacy vote", vote: "yes", weight: Number(contribution.votes.yes) });
        }
        if (Number(contribution.votes.no) > 0) {
          contribution.ballots.push({ voter: "Legacy vote", vote: "no", weight: Number(contribution.votes.no) });
        }
      }
    }
    applyVoteOutcome(contribution);
  });
}

function computeCredits() {
  normalizeContributions();

  const contributorStake = new Map();
  const approvedByModule = new Map();

  MODULES.forEach((module) => approvedByModule.set(module.id, []));
  state.contributions.forEach((contribution) => {
    if (contribution.status === "approved" && approvedByModule.has(contribution.moduleId)) {
      approvedByModule.get(contribution.moduleId).push(contribution);
    }
  });

  const moduleRows = [];
  let contributorOwnedStake = 0;

  MODULES.forEach((module) => {
    const approved = approvedByModule.get(module.id);
    if (approved.length === 0) {
      moduleRows.push({ module, assigned: 0, approvedCount: 0 });
      return;
    }

    const perContribution = module.stake / approved.length;
    contributorOwnedStake += module.stake;
    moduleRows.push({ module, assigned: module.stake, approvedCount: approved.length });

    approved.forEach((contribution) => {
      const current = contributorStake.get(contribution.contributor) || 0;
      contributorStake.set(contribution.contributor, current + perContribution);
    });
  });

  const directorPool = Math.max(0, 100 - contributorOwnedStake);
  const directorStake = directorPool / 2;

  const stakeholderRows = [
    { holder: DIRECTOR_1, stake: directorStake, kind: "director" },
    { holder: DIRECTOR_2, stake: directorStake, kind: "director" },
    ...Array.from(contributorStake.entries()).map(([holder, stake]) => ({ holder, stake, kind: "contributor" }))
  ].sort((a, b) => b.stake - a.stake);

  const totalAssigned = stakeholderRows.reduce((sum, row) => sum + row.stake, 0);

  return {
    stakeholderRows,
    moduleRows,
    contributorOwnedStake,
    directorPool,
    totalAssigned
  };
}

function renderSectionTotals() {
  const sectionTotalsEl = document.getElementById("section-totals");
  const totals = sectionTotals();
  sectionTotalsEl.innerHTML = totals
    .map(
      (item) => `
      <div class="section-cell">
        <div class="section-name">${item.section}</div>
        <div class="section-value">${formatPercent(item.total)}</div>
      </div>
    `
    )
    .join("");
}

function renderSectionsBreakdown() {
  const sectionsContainer = document.getElementById("sections-breakdown");
  if (!sectionsContainer) return;

  sectionsContainer.innerHTML = SECTION_ORDER.map((section) => {
    const modules = MODULES.filter((module) => module.section === section);
    const total = modules.reduce((sum, module) => sum + module.stake, 0);
    const isOpen = expandedSections.has(section);

    return `
      <section class="accordion-item">
        <button class="section-toggle ${isOpen ? "is-open" : ""}" data-section="${section}">
          <span>${section}</span>
          <span>${formatPercent(total)} · ${modules.length} modules</span>
        </button>
        <div class="section-panel ${isOpen ? "is-open" : ""}">
          ${modules
            .map(
              (module) => `
            <article class="module-card">
              <div class="module-head">
                <h4>${module.title}</h4>
                <span>${formatPercent(module.stake)}</span>
              </div>
              <p>${module.deliverables}</p>
              <button class="secondary-btn choose-module-btn" data-module-id="${module.id}">Contribute to this task</button>
            </article>
          `
            )
            .join("")}
        </div>
      </section>
    `;
  }).join("");

  document.querySelectorAll(".section-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const section = button.getAttribute("data-section");
      if (expandedSections.has(section)) {
        expandedSections.delete(section);
      } else {
        expandedSections.add(section);
      }
      renderSectionsBreakdown();
    });
  });

  document.querySelectorAll(".choose-module-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const moduleId = button.getAttribute("data-module-id");
      const moduleSelect = document.getElementById("module-select");
      moduleSelect.value = moduleId;
      setActiveTab("contribute");
      moduleSelect.focus();
      setFormMessage(`Selected: ${moduleById(moduleId).title}`, "ok");
    });
  });
}

function renderModuleSelect() {
  const moduleSelect = document.getElementById("module-select");
  moduleSelect.innerHTML = MODULES.map(
    (module) => `<option value="${module.id}">${module.section} - ${module.title} (${formatPercent(module.stake)})</option>`
  ).join("");
}

function renderPendingAndDecisions() {
  const pendingList = document.getElementById("pending-list");
  const decisionList = document.getElementById("decision-list");
  const voteMessage = document.getElementById("vote-message");
  const creditState = computeCredits();
  const userStake = creditState.stakeholderRows.find((row) => row.holder === USER_VOTER)?.stake || 0;

  const pending = state.contributions
    .filter((item) => item.status === "pending")
    .sort((a, b) => b.createdAt - a.createdAt);

  const decisions = state.contributions
    .filter((item) => item.status !== "pending")
    .sort((a, b) => b.createdAt - a.createdAt);

  if (pending.length === 0) {
    pendingList.innerHTML = '<p class="empty-state">No pending contributions. Submit one in the Contribute tab.</p>';
  } else {
    pendingList.innerHTML = pending
      .map((item) => {
        const module = moduleById(item.moduleId);
        const totals = ballotTotals(item.ballots || []);
        const hasUserVote = (item.ballots || []).some((ballot) => ballot.voter === USER_VOTER);
        const ballotList =
          (item.ballots || []).length > 0
            ? `<ul class="link-list">${item.ballots
                .map((ballot) => `<li>${ballot.voter}: ${ballot.vote.toUpperCase()} (${formatPercent(ballot.weight)})</li>`)
                .join("")}</ul>`
            : '<p class="mini-note">No votes yet.</p>';
        const linksMarkup =
          item.links.length > 0
            ? `<ul class="link-list">${item.links.map((link) => `<li><a href="${link}" target="_blank" rel="noreferrer">${link}</a></li>`).join("")}</ul>`
            : '<p class="mini-note">No links attached.</p>';

        return `
          <article class="submission-card">
            <div class="submission-head">
              <h4>${item.title}</h4>
              <span class="badge pending">Pending</span>
            </div>
            <p class="mini-note"><strong>Contributor:</strong> ${item.contributor}</p>
            <p class="mini-note"><strong>Module:</strong> ${module.title} (${formatPercent(module.stake)})</p>
            <p class="mini-note"><strong>Vote share:</strong> Yes ${formatPercent(totals.yes)} / No ${formatPercent(totals.no)} (decision at >50%)</p>
            <p>${item.summary}</p>
            ${linksMarkup}
            <p class="mini-note"><strong>Ballots:</strong></p>
            ${ballotList}
            <div class="vote-row">
              <button class="primary-btn vote-btn" data-id="${item.id}" data-vote="yes" ${hasUserVote ? "disabled" : ""}>
                Vote Yes as ${USER_VOTER} (+${formatPercent(userStake)})
              </button>
              <button class="secondary-btn vote-btn" data-id="${item.id}" data-vote="no" ${hasUserVote ? "disabled" : ""}>
                Vote No as ${USER_VOTER} (+${formatPercent(userStake)})
              </button>
            </div>
            ${hasUserVote ? '<p class="mini-note">You have already voted on this submission.</p>' : ""}
          </article>
        `;
      })
      .join("");
  }

  if (decisions.length === 0) {
    decisionList.innerHTML = '<p class="empty-state">No decisions yet.</p>';
  } else {
    decisionList.innerHTML = decisions
      .map((item) => {
        const module = moduleById(item.moduleId);
        const totals = ballotTotals(item.ballots || []);
        return `
          <article class="submission-card">
            <div class="submission-head">
              <h4>${item.title}</h4>
              <span class="badge ${item.status}">${item.status === "approved" ? "Approved" : "Rejected"}</span>
            </div>
            <p class="mini-note"><strong>Contributor:</strong> ${item.contributor}</p>
            <p class="mini-note"><strong>Module:</strong> ${module.title}</p>
            <p class="mini-note"><strong>Vote share:</strong> Yes ${formatPercent(totals.yes)} / No ${formatPercent(totals.no)}</p>
          </article>
        `;
      })
      .join("");
  }

  document.querySelectorAll(".vote-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const id = Number(button.getAttribute("data-id"));
      const vote = button.getAttribute("data-vote");
      voteContribution(id, vote);
    });
  });

  if (voteMessage && voteMessage.textContent.trim() === "") {
    setVoteMessage(`Current voting weight for ${USER_VOTER}: ${formatPercent(userStake)}.`, "ok");
  }
}

function renderCredits() {
  const creditSummary = document.getElementById("credit-summary");
  const creditList = document.getElementById("credit-list");
  const moduleStatus = document.getElementById("module-status");
  const result = computeCredits();

  creditSummary.innerHTML = `
    <p><strong>Total assigned stake:</strong> ${formatPercent(result.totalAssigned)}</p>
    <p><strong>Contributor-owned stake:</strong> ${formatPercent(result.contributorOwnedStake)}</p>
    <p><strong>Director-held stake:</strong> ${formatPercent(result.directorPool)} (split between ${DIRECTOR_1} and ${DIRECTOR_2})</p>
  `;

  creditList.innerHTML = `
    <table class="credit-table">
      <thead>
        <tr>
          <th>Stakeholder</th>
          <th>Stake</th>
        </tr>
      </thead>
      <tbody>
        ${result.stakeholderRows
          .map(
            (row) => `
          <tr>
            <td>${row.holder}</td>
            <td>${formatPercent(row.stake)}</td>
          </tr>
        `
          )
          .join("")}
      </tbody>
    </table>
  `;

  moduleStatus.innerHTML = result.moduleRows
    .map((row) => {
      const status = row.approvedCount > 0 ? "Assigned" : "Open";
      return `
        <div class="module-status-row">
          <div>
            <strong>${row.module.title}</strong>
            <p class="mini-note">${row.module.section}</p>
          </div>
          <div class="module-status-meta">
            <span>${formatPercent(row.module.stake)}</span>
            <span class="badge ${status === "Assigned" ? "approved" : "pending"}">${status}</span>
          </div>
        </div>
      `;
    })
    .join("");
}

function setFormMessage(message, type) {
  const formMessage = document.getElementById("form-message");
  formMessage.textContent = message;
  formMessage.classList.remove("is-error", "is-ok");
  if (type === "error") {
    formMessage.classList.add("is-error");
  }
  if (type === "ok") {
    formMessage.classList.add("is-ok");
  }
}

function setVoteMessage(message, type) {
  const voteMessage = document.getElementById("vote-message");
  if (!voteMessage) return;
  voteMessage.textContent = message;
  voteMessage.classList.remove("is-error", "is-ok");
  if (type === "error") {
    voteMessage.classList.add("is-error");
  }
  if (type === "ok") {
    voteMessage.classList.add("is-ok");
  }
}

function addContribution(formData) {
  const contribution = {
    id: state.nextContributionId,
    moduleId: formData.moduleId,
    contributor: formData.contributor.trim(),
    title: formData.title.trim(),
    summary: formData.summary.trim(),
    links: formData.links
      .split("\n")
      .map((item) => item.trim())
      .filter((item) => item.length > 0),
    status: "pending",
    ballots: [],
    createdAt: Date.now()
  };

  state.nextContributionId += 1;
  state.contributions.push(contribution);
  saveState();
}

function voteContribution(contributionId, vote) {
  const contribution = state.contributions.find((item) => item.id === contributionId);
  if (!contribution || contribution.status !== "pending") return;

  const hasUserVote = (contribution.ballots || []).some((ballot) => ballot.voter === USER_VOTER);
  if (hasUserVote) {
    setVoteMessage(`You already voted on "${contribution.title}" as ${USER_VOTER}.`, "error");
    return;
  }

  const creditState = computeCredits();
  const voterStake = creditState.stakeholderRows.find((row) => row.holder === USER_VOTER)?.stake || 0;
  contribution.ballots.push({
    voter: USER_VOTER,
    vote,
    weight: Number(voterStake.toFixed(2)),
    createdAt: Date.now()
  });
  applyVoteOutcome(contribution);

  saveState();
  setVoteMessage(
    `You voted ${vote.toUpperCase()} as ${USER_VOTER} (+${formatPercent(voterStake)}).`,
    "ok"
  );
  renderAll();
}

function bindForm() {
  const form = document.getElementById("contribution-form");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const moduleId = document.getElementById("module-select").value;
    const contributor = document.getElementById("contributor-name").value;
    const title = document.getElementById("contribution-title").value;
    const summary = document.getElementById("contribution-summary").value;
    const links = document.getElementById("contribution-links").value;

    if (!moduleId || !contributor.trim() || !title.trim() || !summary.trim()) {
      setFormMessage("Please fill in all required fields.", "error");
      return;
    }

    addContribution({ moduleId, contributor, title, summary, links });
    form.reset();
    setFormMessage("Contribution submitted to voting queue.", "ok");
    renderAll();
  });
}

function setActiveTab(target) {
  document.querySelectorAll(".tab-btn").forEach((item) => {
    item.classList.toggle("is-active", item.getAttribute("data-view") === target);
  });

  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("is-active", view.id === `view-${target}`);
  });
}

function bindTabs() {
  const tabButtons = document.querySelectorAll(".tab-btn");
  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.getAttribute("data-view");
      setActiveTab(target);
    });
  });
}

function renderTimer() {
  const timer = document.getElementById("reset-timer");
  const remaining = RESET_MS - (Date.now() - Number(state.seededAt));
  if (remaining <= 0) {
    resetState();
    return;
  }
  const minutes = Math.floor(remaining / 60000);
  const seconds = Math.floor((remaining % 60000) / 1000);
  timer.textContent = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function renderAll(optionalMessage) {
  renderSectionTotals();
  renderModuleSelect();
  renderSectionsBreakdown();
  renderPendingAndDecisions();
  renderCredits();
  renderTimer();
  if (optionalMessage) {
    setFormMessage(optionalMessage, "ok");
  }
}

function init() {
  normalizeContributions();
  saveState();
  bindTabs();
  bindForm();
  renderAll();

  setInterval(() => {
    renderTimer();
  }, 1000);
}

init();
