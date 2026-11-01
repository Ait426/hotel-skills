// StayTools 스킬 디렉터리 — 해시 라우팅 단일 페이지 앱
(function () {
  "use strict";

  const SKILLS = Array.isArray(window.SKILLS) ? window.SKILLS : [];
  const app = document.getElementById("app");
  const state = { query: "", tab: "all" };

  // ---------- 공통 유틸 ----------

  function esc(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function formatSize(bytes) {
    if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + "MB";
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + "KB";
    return bytes + "B";
  }

  // 목록·설명에서 쓸 짧은 이름 (staytools- 접두어 제거)
  function shortName(skill) {
    return skill.name.replace(/^staytools-/, "");
  }

  function categories() {
    return [...new Set(SKILLS.map((s) => s.category))];
  }

  function installCommands(skill) {
    const zip = skill.slug + ".zip";
    return {
      powershell: `Expand-Archive .\\${zip} -DestinationPath "$HOME\\.claude\\skills" -Force`,
      unix: `unzip -o ${zip} -d ~/.claude/skills`,
      prompt: `다운로드한 ${zip} 파일을 ~/.claude/skills 폴더에 풀어서 ${skill.name} 스킬을 설치해줘.`,
    };
  }

  // ---------- 클립보드 ----------

  function toast(message) {
    let el = document.querySelector(".toast");
    if (!el) {
      el = document.createElement("div");
      el.className = "toast";
      document.body.appendChild(el);
    }
    el.textContent = message;
    el.classList.add("show");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => el.classList.remove("show"), 1400);
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast("복사했습니다");
    } catch (err) {
      // file:// 등에서 Clipboard API가 막히면 구형 방식으로 다시 시도한다
      console.warn("[copy] Clipboard API 실패, 대체 방식 사용:", err);
      const area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      const ok = document.execCommand("copy");
      area.remove();
      if (ok) {
        toast("복사했습니다");
      } else {
        console.error("[copy] 복사 실패");
        toast("복사에 실패했습니다");
      }
    }
  }

  // ---------- 간단한 마크다운 렌더러 ----------

  function inline(text) {
    let out = esc(text);
    const codes = [];
    // 인라인 코드는 먼저 빼 두어 안쪽이 다른 규칙에 걸리지 않게 한다
    out = out.replace(/`([^`]+)`/g, (_, c) => {
      codes.push(c);
      return `\u0000${codes.length - 1}\u0000`;
    });
    out = out
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
      .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, "$1");
    return out.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[i]}</code>`);
  }

  function splitRow(line) {
    return line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
  }

  function renderMarkdown(src) {
    const lines = src.replace(/\r\n/g, "\n").split("\n");
    const html = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];

      if (/^```/.test(line)) {
        const buf = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
        i++;
        html.push(`<pre><code>${esc(buf.join("\n"))}</code></pre>`);
        continue;
      }

      const heading = line.match(/^(#{1,6})\s+(.*)$/);
      if (heading) {
        const level = Math.min(heading[1].length, 4);
        html.push(`<h${level}>${inline(heading[2])}</h${level}>`);
        i++;
        continue;
      }

      if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
        html.push("<hr>");
        i++;
        continue;
      }

      // 표: 헤더 줄 다음에 구분선(|---|) 줄이 있어야 한다
      if (line.includes("|") && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
        const head = splitRow(line);
        i += 2;
        const rows = [];
        while (i < lines.length && lines[i].includes("|") && lines[i].trim()) rows.push(splitRow(lines[i++]));
        html.push(
          "<table><thead><tr>" + head.map((h) => `<th>${inline(h)}</th>`).join("") + "</tr></thead><tbody>" +
          rows.map((r) => "<tr>" + r.map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>").join("") +
          "</tbody></table>"
        );
        continue;
      }

      if (/^>\s?/.test(line)) {
        const buf = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, ""));
        html.push(`<blockquote>${inline(buf.join(" "))}</blockquote>`);
        continue;
      }

      const list = line.match(/^(\s*)([-*+]|\d+[.)])\s+/);
      if (list) {
        const ordered = /\d/.test(list[2]);
        const items = [];
        while (i < lines.length) {
          const m = lines[i].match(/^\s*([-*+]|\d+[.)])\s+(.*)$/);
          if (m) {
            items.push(m[2]);
          } else if (/^\s{2,}\S/.test(lines[i]) && items.length) {
            // 들여쓴 이어지는 줄은 앞 항목에 붙인다
            items[items.length - 1] += " " + lines[i].trim();
          } else {
            break;
          }
          i++;
        }
        const tag = ordered ? "ol" : "ul";
        html.push(`<${tag}>` + items.map((t) => `<li>${inline(t)}</li>`).join("") + `</${tag}>`);
        continue;
      }

      if (!line.trim()) {
        i++;
        continue;
      }

      const buf = [];
      while (
        i < lines.length && lines[i].trim() &&
        !/^(#{1,6}\s|```|>|\s*([-*+]|\d+[.)])\s)/.test(lines[i])
      ) buf.push(lines[i++]);
      html.push(`<p>${inline(buf.join(" "))}</p>`);
    }
    return html.join("\n");
  }

  // ---------- 홈 (리더보드) ----------

  function filtered() {
    const q = state.query.trim().toLowerCase();
    let list = SKILLS.filter((s) =>
      !q || [s.name, s.description, s.category].some((v) => v.toLowerCase().includes(q))
    );
    if (state.tab === "recent") {
      list = [...list].sort((a, b) => b.updated.localeCompare(a.updated));
    } else if (state.tab !== "all") {
      list = list.filter((s) => s.category === state.tab);
    }
    return list;
  }

  function fileBars(count) {
    const max = Math.max(...SKILLS.map((s) => s.files.length));
    const on = Math.max(1, Math.round((count / max) * 16));
    return '<div class="bars">' +
      Array.from({ length: 16 }, (_, k) => `<i class="${k < on ? "on" : ""}" style="height:${30 + ((k * 37) % 70)}%"></i>`).join("") +
      "</div>";
  }

  function renderRows() {
    const list = filtered();
    const body = document.getElementById("rows");
    if (!body) return;
    if (!list.length) {
      body.innerHTML = `<tr><td colspan="4" class="empty">"${esc(state.query)}"에 맞는 스킬이 없습니다</td></tr>`;
      return;
    }
    body.innerHTML = list.map((s, idx) => `
      <tr class="row" data-slug="${esc(s.slug)}">
        <td class="rank">${idx + 1}</td>
        <td>
          <span class="skill-name">${esc(shortName(s))}</span><span class="skill-sub">${esc(s.category)}</span>
          <div class="skill-target">대상: ${esc(s.target)}</div>
        </td>
        <td class="hide-sm">${fileBars(s.files.length)}</td>
        <td class="num">${formatSize(s.zipSize)}</td>
      </tr>`).join("");
  }

  function renderTabs() {
    const tabs = [["all", `전체 (${SKILLS.length})`], ["recent", "최근 수정"], ...categories().map((c) => [c, c])];
    document.getElementById("tabs").innerHTML = tabs
      .map(([key, label]) => `<button data-tab="${esc(key)}" class="${state.tab === key ? "on" : ""}">${esc(label)}</button>`)
      .join("");
  }

  function renderHome() {
    document.title = "StayTools 스킬 디렉터리";
    app.innerHTML = `
      <section class="hero">
        <div>
          <h1 class="logo">STAY<br>TOOLS</h1>
          <p class="eyebrow">호텔 운영 에이전트 스킬 모음</p>
          <div class="try">
            <p class="label">바로 설치</p>
            <div class="cmd">
              <code><span class="prompt">PS&gt; </span>Expand-Archive .\\&lt;스킬&gt;.zip -DestinationPath "$HOME\\.claude\\skills"</code>
              <button class="copy" data-copy='Expand-Archive .\\<스킬>.zip -DestinationPath "$HOME\\.claude\\skills"'>복사</button>
            </div>
          </div>
        </div>
        <div>
          <p class="tagline">스킬은 AI 에이전트에 붙이는 <b>재사용 가능한 업무 지식</b>입니다. zip을 내려받아 설치하고 <b>내 숙소 값</b>을 알려 주면 OTA 요금·입금가 계산, 재고 대조, 청소 배정 같은 호텔 운영 절차를 에이전트가 따라 합니다. 스킬마다 필요한 채널과 입력값이 다르니 상세 페이지의 <b>사용 조건</b>을 먼저 확인하세요.</p>
          <div class="try">
            <p class="label">사용 가능한 에이전트</p>
            <div class="agents">
              <span class="chip">Claude Code</span>
              <span class="chip">Claude 데스크톱</span>
              <span class="chip">Claude.ai</span>
            </div>
          </div>
        </div>
      </section>

      <section class="board">
        <p class="label">스킬 목록</p>
        <label class="search">
          <span aria-hidden="true">⌕</span>
          <input id="q" type="search" placeholder="스킬 검색..." value="${esc(state.query)}" autocomplete="off">
          <kbd>/</kbd>
        </label>
        <div class="tabs" id="tabs"></div>
        <table class="table">
          <thead><tr><th>#</th><th>스킬</th><th class="hide-sm">구성 파일</th><th class="num">용량</th></tr></thead>
          <tbody id="rows"></tbody>
        </table>
      </section>`;
    renderTabs();
    renderRows();
  }

  // ---------- 상세 ----------

  function renderDetail(slug) {
    const skill = SKILLS.find((s) => s.slug === slug);
    if (!skill) {
      app.innerHTML = `<p class="empty">스킬을 찾을 수 없습니다: ${esc(slug)} · <a href="#/">목록으로</a></p>`;
      return;
    }
    document.title = `${shortName(skill)} — StayTools`;
    const cmds = installCommands(skill);
    const related = SKILLS.filter((s) => s.category === skill.category && s.slug !== skill.slug);

    app.innerHTML = `
      <nav class="crumbs"><a href="#/">스킬</a><span>/</span>${esc(skill.category)}<span>/</span>${esc(shortName(skill))}</nav>
      <div class="detail">
        <article>
          <h1>${esc(shortName(skill))}</h1>
          <p class="cat">${esc(skill.category)}</p>

          <section>
            <div class="section-head">
              <p class="label">설치</p>
              <div class="seg" id="cmd-seg">
                <button data-cmd="powershell" class="on">PowerShell</button>
                <button data-cmd="unix">macOS·Linux</button>
                <button data-cmd="prompt">프롬프트</button>
              </div>
            </div>
            <div class="cmd">
              <code id="cmd-text"></code>
              <button class="copy" id="cmd-copy">복사</button>
            </div>
          </section>

          <section class="section">
            <p class="label">요약</p>
            <div class="summary">${esc(skill.description)}</div>
          </section>

          <section class="section">
            <p class="label">사용 조건</p>
            <dl class="req">
              <dt>대상</dt>
              <dd>${esc(skill.target)}</dd>
              <dt>필요한 시스템</dt>
              <dd>${skill.systems.length ? skill.systems.map(esc).join(" · ") : "없음"}</dd>
              <dt>준비할 입력</dt>
              <dd><ul>${skill.inputs.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></dd>
              <dt>알아 둘 점</dt>
              <dd><ul>${skill.notes.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></dd>
            </dl>
          </section>

          <section class="section">
            <div class="section-head">
              <p class="label">문서</p>
              <div class="seg" id="doc-seg">
                <button data-doc="body" class="on">SKILL.md</button>
                ${skill.guide ? '<button data-doc="guide">사용 안내</button>' : ""}
              </div>
            </div>
            <div class="md clamp" id="doc"></div>
            <button class="more" id="more">더 보기</button>
          </section>

          ${related.length ? `
          <section class="section">
            <p class="label">같은 카테고리 · ${esc(skill.category)}</p>
            <div class="related">
              ${related.map((r) => `<a class="card" href="#/s/${esc(r.slug)}"><b>${esc(shortName(r))}</b><p>${esc(r.description)}</p></a>`).join("")}
            </div>
          </section>` : ""}
        </article>

        <aside class="side">
          <div>
            <p class="label">다운로드</p>
            <a class="download" href="${esc(skill.zip)}" download>↓ ${esc(skill.slug)}.zip</a>
            <p class="label" style="margin-top:8px">${formatSize(skill.zipSize)} · 파일 ${skill.files.length}개</p>
          </div>
          <div><p class="label">SKILL.md 분량</p><div class="big">${skill.lines}줄</div></div>
          <div><p class="label">최근 수정</p><div class="val">${esc(skill.updated)}</div></div>
          <div>
            <p class="label">구성 파일</p>
            <ul class="files">${skill.files.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
          </div>
        </aside>
      </div>`;

    // 설치 명령 전환
    const cmdText = document.getElementById("cmd-text");
    let current = "powershell";
    const showCmd = (key) => {
      current = key;
      cmdText.textContent = cmds[key];
      document.querySelectorAll("#cmd-seg button").forEach((b) => b.classList.toggle("on", b.dataset.cmd === key));
    };
    document.getElementById("cmd-seg").addEventListener("click", (e) => {
      if (e.target.dataset.cmd) showCmd(e.target.dataset.cmd);
    });
    document.getElementById("cmd-copy").addEventListener("click", () => copyText(cmds[current]));
    showCmd("powershell");

    // 문서 전환 + 더 보기
    const doc = document.getElementById("doc");
    const more = document.getElementById("more");
    const showDoc = (key) => {
      doc.innerHTML = renderMarkdown(skill[key] || "");
      doc.classList.add("clamp");
      more.style.display = doc.scrollHeight > 600 ? "" : "none";
      document.querySelectorAll("#doc-seg button").forEach((b) => b.classList.toggle("on", b.dataset.doc === key));
    };
    document.getElementById("doc-seg").addEventListener("click", (e) => {
      if (e.target.dataset.doc) showDoc(e.target.dataset.doc);
    });
    more.addEventListener("click", () => {
      doc.classList.remove("clamp");
      more.style.display = "none";
    });
    showDoc("body");
  }

  // ---------- 설치 방법 ----------

  function renderInstall() {
    document.title = "설치 방법 — StayTools";
    app.innerHTML = `
      <nav class="crumbs"><a href="#/">스킬</a><span>/</span>설치 방법</nav>
      <div class="detail" style="grid-template-columns:1fr">
        <article>
          <h1>설치 방법</h1>
          <p class="cat">zip을 내려받아 스킬 폴더에 풀면 끝입니다.</p>
          <div class="md">${renderMarkdown([
            "## 1. 내려받기",
            "스킬 목록에서 원하는 스킬을 열고 오른쪽의 **다운로드** 버튼을 누릅니다.",
            "## 2. 스킬 폴더에 풀기",
            "Claude Code는 `~/.claude/skills/<스킬명>/SKILL.md` 위치의 스킬을 자동으로 읽습니다.",
            "```",
            'Expand-Archive .\\staytools-agoda-audit.zip -DestinationPath "$HOME\\.claude\\skills" -Force',
            "```",
            "macOS·Linux는 `unzip -o <파일>.zip -d ~/.claude/skills` 를 씁니다.",
            "## 3. 숙소 정보 채우기",
            "스킬마다 필요한 채널과 입력값이 다릅니다. 상세 페이지의 **사용 조건**을 확인하세요. 일부 스킬에는 `hotel-profile.example.md` 같은 예시 파일이 있습니다. 내 숙소 값으로 채워 쓰고, **비밀번호·토큰·투숙객 정보는 넣지 않습니다.**",
            "## 4. 확인",
            "Claude Code를 다시 열고 스킬 이름이나 관련 업무(예: \"아고다 입금가 점검해줘\")를 말하면 스킬이 동작합니다.",
          ].join("\n"))}</div>
        </article>
      </div>`;
  }

  // ---------- 라우터·이벤트 ----------

  function route() {
    const hash = location.hash.replace(/^#/, "") || "/";
    const detail = hash.match(/^\/s\/([^/]+)$/);
    try {
      if (detail) renderDetail(decodeURIComponent(detail[1]));
      else if (hash === "/install") renderInstall();
      else renderHome();
    } catch (err) {
      console.error("[route] 화면 렌더링 실패:", hash, err);
      app.innerHTML = `<p class="empty">화면을 그리는 중 오류가 났습니다. 콘솔을 확인하세요.</p>`;
    }
    window.scrollTo(0, 0);
  }

  app.addEventListener("click", (e) => {
    const copyBtn = e.target.closest("[data-copy]");
    if (copyBtn) return copyText(copyBtn.dataset.copy);

    const tab = e.target.closest("[data-tab]");
    if (tab) {
      state.tab = tab.dataset.tab;
      renderTabs();
      renderRows();
      return;
    }

    const row = e.target.closest("tr.row");
    if (row) location.hash = "#/s/" + encodeURIComponent(row.dataset.slug);
  });

  app.addEventListener("input", (e) => {
    if (e.target.id === "q") {
      state.query = e.target.value;
      renderRows();
    }
  });

  // "/" 키로 검색창 포커스
  document.addEventListener("keydown", (e) => {
    const q = document.getElementById("q");
    if (e.key === "/" && q && document.activeElement !== q) {
      e.preventDefault();
      q.focus();
    }
  });

  if (!SKILLS.length) console.error("[init] data.js에 스킬이 없습니다. build.py를 먼저 실행하세요.");
  document.getElementById("footer-count").textContent = `스킬 ${SKILLS.length}개`;
  window.addEventListener("hashchange", route);
  route();
})();
