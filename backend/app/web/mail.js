const $ = selector => document.querySelector(selector);
const state = {
  token: sessionStorage.seldruneMailToken || "",
  organizationId: "",
  user: null,
  membership: null,
  workspace: null,
  mailboxId: "",
  view: "inbox",
  editingDraftId: ""
};

async function request(path, options) {
  const opts = options || {};
  const headers = Object.assign({"Content-Type":"application/json"}, opts.headers || {});
  if (state.token) headers.Authorization = "Bearer " + state.token;
  const response = await fetch("/api/v1" + path, Object.assign({}, opts, {headers:headers}));
  if (response.status === 401 && path !== "/auth/login") {
    logout();
    throw new Error("Your session expired. Sign in again.");
  }
  if (response.status === 204) return null;
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Request failed (" + response.status + ")");
  }
  return response.json();
}

function orgPath(path) {
  return "/organizations/" + encodeURIComponent(state.organizationId) + "/mail" + path;
}

function flash(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2800);
}

function setError(message) {
  $("#login-error").textContent = message || "";
}

function logout() {
  state.token = "";
  state.organizationId = "";
  state.user = null;
  state.membership = null;
  state.workspace = null;
  sessionStorage.removeItem("seldruneMailToken");
  $("#login-password").value = "";
  $("#mail-app").classList.add("hidden");
  $("#login-view").classList.remove("hidden");
}

async function establishSession() {
  const me = await request("/auth/me");
  const memberships = me.memberships || [];
  if (!memberships.length) throw new Error("Your account is not part of a Seldrune organization yet.");
  state.user = me.user;
  state.membership = memberships.find(item => item.role === "owner") || memberships[0];
  state.organizationId = state.membership.organization.id;
  $("#profile-name").textContent = me.user.display_name || me.user.email;
  $("#profile-org").textContent = state.membership.organization.name;
  $("#profile-avatar").textContent = (me.user.display_name || me.user.email || "S").slice(0,1).toUpperCase();
  $("#login-view").classList.add("hidden");
  $("#mail-app").classList.remove("hidden");
  await loadWorkspace();
}

async function loadWorkspace() {
  state.workspace = await request(orgPath("/workspace"));
  $("#provider-state").textContent = state.workspace.delivery.ready ? "Mail host connected" : "Host setup needed";
  $("#compose-open").disabled = !state.workspace.mailboxes.some(item => item.access === "owner" || item.access === "write");
  renderMailboxSidebar();
  renderCurrentView();
}

function renderMailboxSidebar() {
  const root = $("#mailbox-list");
  root.replaceChildren();
  const items = state.workspace.mailboxes || [];
  if (!state.mailboxId && items.length) state.mailboxId = items[0].id;
  if (!items.some(item => item.id === state.mailboxId)) state.mailboxId = items.length ? items[0].id : "";
  items.forEach(item => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "mailbox-item" + (item.id === state.mailboxId ? " selected" : "");
    button.addEventListener("click", () => {
      state.mailboxId = item.id;
      renderMailboxSidebar();
      state.view = "inbox";
      renderCurrentView();
    });
    const icon = document.createElement("span");
    icon.className = "mailbox-letter";
    icon.textContent = item.email_address.slice(0,1).toUpperCase();
    const copy = document.createElement("span");
    copy.className = "mailbox-copy";
    const name = document.createElement("strong");
    name.textContent = item.display_name;
    const address = document.createElement("small");
    address.textContent = item.email_address;
    copy.append(name, address);
    button.append(icon, copy);
    root.append(button);
  });
}

function setActiveNav() {
  document.querySelectorAll(".mail-nav button").forEach(button => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });
}

function makeEmpty(icon, title, message, buttonText, action) {
  const card = document.createElement("div");
  card.className = "empty-card";
  const inner = document.createElement("div");
  const glyph = document.createElement("div");
  glyph.className = "empty-icon";
  glyph.textContent = icon;
  const heading = document.createElement("h2");
  heading.textContent = title;
  const paragraph = document.createElement("p");
  paragraph.textContent = message;
  inner.append(glyph, heading, paragraph);
  if (buttonText) {
    const actions = document.createElement("div");
    actions.className = "hero-actions";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "primary";
    button.textContent = buttonText;
    button.addEventListener("click", action);
    actions.append(button);
    inner.append(actions);
  }
  card.append(inner);
  return card;
}

function renderCurrentView() {
  if (!state.workspace) return;
  setActiveNav();
  const title = {inbox:"Inbox",drafts:"Drafts",sent:"Sent",shared:"Shared mailboxes",settings:"Domains & access"}[state.view] || "Inbox";
  $("#view-title").textContent = title;
  const root = $("#mail-content");
  root.replaceChildren();

  if (state.workspace.setup_required) {
    const card = document.createElement("section");
    card.className = "hero-card onboarding";
    const copy = document.createElement("div");
    const eyebrow = document.createElement("p");
    eyebrow.className = "eyebrow";
    eyebrow.textContent = "MAIL WORKSPACE SETUP";
    const heading = document.createElement("h2");
    heading.textContent = "Set up Seldrune’s shared addresses";
    const message = document.createElement("p");
    message.textContent = "Start with seldrune.in and the addresses you planned. Owners will share every mailbox automatically; you can grant other organization members access individually.";
    const actions = document.createElement("div");
    actions.className = "hero-actions";
    const setup = document.createElement("button");
    setup.className = "primary";
    setup.type = "button";
    setup.textContent = "Initialize Seldrune Mail";
    setup.addEventListener("click", initializeWorkspace);
    actions.append(setup);
    copy.append(eyebrow, heading, message, actions);
    card.append(copy);
    root.append(card);
    return;
  }

  if (state.view === "settings") {
    renderSettings(root);
    return;
  }
  if (state.view === "shared") {
    renderShared(root);
    return;
  }
  if (state.view === "drafts") {
    renderDrafts(root);
    return;
  }
  const message = state.view === "sent"
    ? "Sent messages will appear here after an outbound mail host is connected."
    : "Your Seldrune addresses are created, but no mail host is attached yet. Connect a mail host and configure its MX, SPF, and DKIM records to receive external email.";
  const card = makeEmpty(state.view === "sent" ? "↗" : "✉", state.view === "sent" ? "Sent mail is waiting for a host" : "Your inbox is ready for its mail host", message, "Open domain & access setup", () => {
    state.view = "settings";
    renderCurrentView();
  });
  root.append(card);
  if (!state.workspace.mailboxes.length) root.append(makeEmpty("＋", "Create a mailbox", "Initialize your Seldrune Mail workspace to create shared addresses.", null));
}

async function initializeWorkspace() {
  try {
    state.workspace = await request(orgPath("/setup"), {method:"POST", body:"{}"});
    state.mailboxId = state.workspace.mailboxes.length ? state.workspace.mailboxes[0].id : "";
    renderMailboxSidebar();
    renderCurrentView();
    flash("Seldrune Mail workspace created");
  } catch (error) {
    flash(error.message);
  }
}

function renderShared(root) {
  if (!state.workspace.mailboxes.length) {
    root.append(makeEmpty("◎", "No mailboxes yet", "Initialize the workspace to create shared Seldrune addresses.", "Set up mail", initializeWorkspace));
    return;
  }
  const intro = document.createElement("section");
  intro.className = "hero-card";
  const copy = document.createElement("div");
  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "TEAM MAILBOXES";
  const heading = document.createElement("h2");
  heading.textContent = "One shared view for the team";
  const paragraph = document.createElement("p");
  paragraph.textContent = "Every organization owner can open every mailbox. Managers can grant read or write access to other organization members.";
  copy.append(eyebrow, heading, paragraph);
  intro.append(copy);
  root.append(intro);
  const headingRow = document.createElement("div");
  headingRow.className = "section-title";
  const section = document.createElement("h2");
  section.textContent = "Available mailboxes";
  headingRow.append(section);
  root.append(headingRow);
  const grid = document.createElement("div");
  grid.className = "mailbox-grid";
  state.workspace.mailboxes.forEach(item => {
    const card = document.createElement("article");
    card.className = "mailbox-card";
    const name = document.createElement("h3");
    name.textContent = item.display_name;
    const address = document.createElement("p");
    address.textContent = item.email_address;
    const meta = document.createElement("div");
    meta.className = "mailbox-meta";
    const status = document.createElement("span");
    status.className = "status-tag";
    status.textContent = "Host required";
    const access = document.createElement("span");
    access.className = "status-tag success";
    access.textContent = item.access === "owner" ? "Owner access" : item.access + " access";
    meta.append(status, access);
    card.append(name, address, meta);
    grid.append(card);
  });
  root.append(grid);
}

async function renderDrafts(root) {
  if (!state.mailboxId) {
    root.append(makeEmpty("✎", "Choose a mailbox", "Set up Seldrune Mail before saving drafts.", "Set up mail", initializeWorkspace));
    return;
  }
  const intro = document.createElement("div");
  intro.className = "section-title";
  const copy = document.createElement("div");
  const heading = document.createElement("h2");
  heading.textContent = "Saved drafts";
  const sub = document.createElement("p");
  sub.textContent = "Encrypted at rest and shared with people who can access this mailbox.";
  copy.append(heading, sub);
  const compose = document.createElement("button");
  compose.type = "button";
  compose.className = "primary";
  compose.textContent = "New draft";
  compose.disabled = !canWriteMailbox(state.mailboxId);
  compose.addEventListener("click", () => openCompose());
  intro.append(copy, compose);
  root.append(intro);
  try {
    const drafts = await request(orgPath("/mailboxes/" + encodeURIComponent(state.mailboxId) + "/drafts"));
    $("#draft-count").textContent = String(drafts.length);
    if (!drafts.length) {
      root.append(makeEmpty("✎", "No drafts yet", "Compose a message and save it here. Sending unlocks when a mail host is connected.", "Compose a draft", () => openCompose()));
      return;
    }
    const list = document.createElement("div");
    list.className = "list-card";
    drafts.forEach(draft => {
      const row = document.createElement("div");
      row.className = "draft-row";
      const open = document.createElement("button");
      open.type = "button";
      open.className = "draft-open";
      const subject = document.createElement("strong");
      subject.textContent = draft.subject || "(no subject)";
      const details = document.createElement("small");
      details.textContent = "To: " + (draft.to || []).join(", ") + " · " + (draft.updated_at ? new Date(draft.updated_at).toLocaleString() : "");
      open.append(subject, details);
      open.addEventListener("click", () => openCompose(draft));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "small-button";
      remove.textContent = "Delete";
      remove.addEventListener("click", async () => {
        try {
          await request(orgPath("/mailboxes/" + encodeURIComponent(state.mailboxId) + "/drafts/" + encodeURIComponent(draft.id)), {method:"DELETE"});
          flash("Draft deleted");
          renderCurrentView();
        } catch (error) { flash(error.message); }
      });
      row.append(open, remove);
      list.append(row);
    });
    root.append(list);
  } catch (error) {
    root.append(makeEmpty("!", "Drafts unavailable", error.message, null));
  }
}

function renderSettings(root) {
  const grid = document.createElement("div");
  grid.className = "settings-grid";
  const domainsCard = document.createElement("section");
  domainsCard.className = "settings-card";
  const domainTitle = document.createElement("h2");
  domainTitle.textContent = "Custom domains";
  const domainInfo = document.createElement("p");
  domainInfo.textContent = "Prove control of a domain with a TXT record. Mail delivery remains off until an email host is connected and its provider records are installed.";
  domainsCard.append(domainTitle, domainInfo);
  (state.workspace.domains || []).forEach(domain => {
    const row = document.createElement("div");
    row.className = "domain-row";
    const copy = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = domain.domain;
    const recordName = document.createElement("small");
    recordName.textContent = "TXT name: " + domain.verification_record_name;
    const value = document.createElement("small");
    value.className = "dns-value";
    value.textContent = domain.verification_record_value || "Verification value is available to mail managers.";
    copy.append(name, recordName, value);
    row.append(copy);
    if (domain.status !== "verified" && state.workspace.can_manage) {
      const verify = document.createElement("button");
      verify.type = "button";
      verify.className = "small-button";
      verify.textContent = "Check TXT";
      verify.addEventListener("click", () => verifyDomain(domain.id));
      row.append(verify);
    } else {
      const status = document.createElement("span");
      status.className = "status-tag" + (domain.status === "verified" ? " success" : "");
      status.textContent = domain.status === "verified" ? "Verified" : "Pending";
      row.append(status);
    }
    domainsCard.append(row);
  });
  if (state.workspace.can_manage) {
    const form = document.createElement("form");
    form.id = "domain-form";
    const label = document.createElement("label");
    label.textContent = "Add another domain";
    const input = document.createElement("input");
    input.name = "domain";
    input.placeholder = "example.com";
    input.required = true;
    label.append(input);
    const button = document.createElement("button");
    button.type = "submit";
    button.className = "primary";
    button.textContent = "Add domain";
    form.append(label, button);
    form.addEventListener("submit", addDomain);
    domainsCard.append(form);
  }

  const deliveryCard = document.createElement("section");
  deliveryCard.className = "settings-card";
  const deliveryTitle = document.createElement("h2");
  deliveryTitle.textContent = "Mail host connection";
  const deliveryInfo = document.createElement("p");
  deliveryInfo.textContent = "No mail host is configured. Choose a provider such as Microsoft 365, Google Workspace, or another supported email host. Seldrune can then use the provider’s delivery and inbox services while keeping shared access in this workspace.";
  const deliveryTag = document.createElement("div");
  deliveryTag.className = "domain-row";
  const deliveryCopy = document.createElement("div");
  const deliveryName = document.createElement("strong");
  deliveryName.textContent = "Inbound and outbound mail";
  const deliveryState = document.createElement("small");
  deliveryState.textContent = "Inactive until provider credentials and DNS records are configured.";
  deliveryCopy.append(deliveryName, deliveryState);
  const tag = document.createElement("span");
  tag.className = "status-tag";
  tag.textContent = "Not connected";
  deliveryTag.append(deliveryCopy, tag);
  deliveryCard.append(deliveryTitle, deliveryInfo, deliveryTag);

  const mailboxCard = document.createElement("section");
  mailboxCard.className = "settings-card";
  const mailboxTitle = document.createElement("h2");
  mailboxTitle.textContent = "Mailbox identities";
  const mailboxInfo = document.createElement("p");
  mailboxInfo.textContent = "Addresses are prepared for the domain. They will receive messages once its mail host and DNS are active.";
  mailboxCard.append(mailboxTitle, mailboxInfo);
  state.workspace.mailboxes.forEach(mailbox => {
    const row = document.createElement("div");
    row.className = "member-row";
    const info = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = mailbox.email_address;
    const subtitle = document.createElement("small");
    subtitle.textContent = mailbox.display_name;
    info.append(name, subtitle);
    const status = document.createElement("span");
    status.className = "status-tag";
    status.textContent = mailbox.access === "owner" ? "All owners" : mailbox.access;
    row.append(info, status);
    mailboxCard.append(row);
    if (state.workspace.can_manage) appendShareForm(mailboxCard, mailbox);
  });
  if (state.workspace.can_manage && state.workspace.domains.length) {
    const form = document.createElement("form");
    form.id = "mailbox-form";
    const localLabel = document.createElement("label");
    localLabel.textContent = "New address";
    const localInput = document.createElement("input");
    localInput.name = "local_part";
    localInput.placeholder = "team";
    localInput.required = true;
    localLabel.append(localInput);
    const displayLabel = document.createElement("label");
    displayLabel.textContent = "Display name";
    const displayInput = document.createElement("input");
    displayInput.name = "display_name";
    displayInput.placeholder = "Seldrune Team";
    displayInput.required = true;
    displayLabel.append(displayInput);
    const domainLabel = document.createElement("label");
    domainLabel.textContent = "Domain";
    const select = document.createElement("select");
    select.name = "domain_id";
    state.workspace.domains.forEach(domain => {
      const option = document.createElement("option");
      option.value = domain.id;
      option.textContent = domain.domain;
      select.append(option);
    });
    domainLabel.append(select);
    const button = document.createElement("button");
    button.type = "submit";
    button.className = "primary";
    button.textContent = "Create mailbox";
    form.append(localLabel, displayLabel, domainLabel, button);
    form.addEventListener("submit", createMailbox);
    mailboxCard.append(form);
  }

  const membersCard = document.createElement("section");
  membersCard.className = "settings-card";
  const membersTitle = document.createElement("h2");
  membersTitle.textContent = "Organization owners";
  const membersInfo = document.createElement("p");
  membersInfo.textContent = "Every owner has full access to every mailbox. Grant other members access from the mailbox list.";
  membersCard.append(membersTitle, membersInfo);
  (state.workspace.members || []).filter(member => member.role === "owner").forEach(member => {
    const row = document.createElement("div");
    row.className = "member-row";
    const info = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = member.display_name;
    const email = document.createElement("small");
    email.textContent = member.email;
    info.append(name, email);
    const tag = document.createElement("span");
    tag.className = "status-tag success";
    tag.textContent = "All mailboxes";
    row.append(info, tag);
    membersCard.append(row);
  });

  grid.append(domainsCard, deliveryCard, mailboxCard, membersCard);
  root.append(grid);
}

function appendShareForm(parent, mailbox) {
  const shareList = document.createElement("div");
  shareList.className = "share-list";
  (mailbox.shared_with || []).forEach(person => {
    const row = document.createElement("div");
    row.className = "member-row";
    const info = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = person.display_name;
    const email = document.createElement("small");
    email.textContent = person.email + " · " + person.permission;
    info.append(name, email);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "small-button";
    remove.textContent = "Remove";
    remove.addEventListener("click", async () => {
      try {
        await request(orgPath("/mailboxes/" + encodeURIComponent(mailbox.id) + "/access/" + encodeURIComponent(person.user_id)), {method:"DELETE"});
        await loadWorkspace();
        state.view = "settings";
        renderCurrentView();
        flash("Mailbox access removed");
      } catch (error) { flash(error.message); }
    });
    row.append(info, remove);
    shareList.append(row);
  });
  parent.append(shareList);
  const form = document.createElement("form");
  form.className = "share-form";
  const email = document.createElement("input");
  email.type = "email";
  email.name = "email";
  email.placeholder = "Member email";
  email.required = true;
  const permission = document.createElement("select");
  permission.name = "permission";
  [["write","Can read and write"],["read","Read only"]].forEach(entry => {
    const option = document.createElement("option");
    option.value = entry[0];
    option.textContent = entry[1];
    permission.append(option);
  });
  const button = document.createElement("button");
  button.type = "submit";
  button.textContent = "Share access";
  form.append(email, permission, button);
  form.addEventListener("submit", event => shareMailbox(event, mailbox.id));
  parent.append(form);
}

async function addDomain(event) {
  event.preventDefault();
  const domain = new FormData(event.currentTarget).get("domain");
  try {
    await request(orgPath("/domains"), {method:"POST", body:JSON.stringify({domain:domain})});
    await loadWorkspace();
    state.view = "settings";
    renderCurrentView();
    flash("Domain added. Add its TXT record to verify control.");
  } catch (error) { flash(error.message); }
}

async function verifyDomain(id) {
  try {
    await request(orgPath("/domains/" + encodeURIComponent(id) + "/verify"), {method:"POST", body:"{}"});
    await loadWorkspace();
    state.view = "settings";
    renderCurrentView();
    flash("Domain ownership verified");
  } catch (error) { flash(error.message); }
}

async function createMailbox(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    local_part:form.get("local_part"),
    display_name:form.get("display_name"),
    domain_id:form.get("domain_id")
  };
  try {
    await request(orgPath("/mailboxes"), {method:"POST", body:JSON.stringify(payload)});
    await loadWorkspace();
    state.view = "settings";
    renderCurrentView();
    flash("Mailbox identity created");
  } catch (error) { flash(error.message); }
}

async function shareMailbox(event, mailboxId) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  try {
    await request(orgPath("/mailboxes/" + encodeURIComponent(mailboxId) + "/access"), {
      method:"POST",
      body:JSON.stringify({email:form.get("email"), permission:form.get("permission")})
    });
    await loadWorkspace();
    state.view = "settings";
    renderCurrentView();
    flash("Mailbox access updated");
  } catch (error) { flash(error.message); }
}

function splitEmails(value) {
  return value.split(/[;,]/).map(item => item.trim()).filter(Boolean);
}

function canWriteMailbox(mailboxId) {
  const mailbox = state.workspace.mailboxes.find(item => item.id === mailboxId);
  return Boolean(mailbox && (mailbox.access === "owner" || mailbox.access === "write"));
}

function openCompose(draft) {
  const mailboxId = draft ? state.mailboxId : state.mailboxId;
  const readOnly = !canWriteMailbox(mailboxId);
  const dialog = $("#compose-dialog");
  state.editingDraftId = draft && !readOnly ? draft.id : "";
  $("#compose-title").textContent = readOnly ? "View draft" : draft ? "Edit draft" : "New message";
  const mailboxSelect = $("#compose-mailbox");
  mailboxSelect.replaceChildren();
  state.workspace.mailboxes.filter(item => item.access === "owner" || item.access === "write").forEach(item => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.email_address;
    mailboxSelect.append(option);
  });
  if (state.mailboxId) mailboxSelect.value = state.mailboxId;
  $("#compose-to").value = draft ? (draft.to || []).join(", ") : "";
  $("#compose-cc").value = draft ? (draft.cc || []).join(", ") : "";
  $("#compose-bcc").value = draft ? (draft.bcc || []).join(", ") : "";
  $("#compose-subject").value = draft ? draft.subject || "" : "";
  $("#compose-body").value = draft ? draft.body || "" : "";
  ["#compose-mailbox","#compose-to","#compose-cc","#compose-bcc","#compose-subject","#compose-body"].forEach(selector => {
    $(selector).disabled = readOnly;
  });
  $("#compose-form button[type=submit]").disabled = readOnly;
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
}

function closeCompose() {
  const dialog = $("#compose-dialog");
  if (typeof dialog.close === "function") dialog.close();
  else dialog.removeAttribute("open");
  $("#compose-form").reset();
  ["#compose-mailbox","#compose-to","#compose-cc","#compose-bcc","#compose-subject","#compose-body"].forEach(selector => {
    $(selector).disabled = false;
  });
  $("#compose-form button[type=submit]").disabled = false;
  state.editingDraftId = "";
}

async function saveDraft(event) {
  event.preventDefault();
  const mailboxId = $("#compose-mailbox").value;
  const payload = {
    to:splitEmails($("#compose-to").value),
    cc:splitEmails($("#compose-cc").value),
    bcc:splitEmails($("#compose-bcc").value),
    subject:$("#compose-subject").value,
    body:$("#compose-body").value
  };
  if (!payload.to.length) {
    flash("Add at least one recipient to save this draft.");
    return;
  }
  try {
    const suffix = state.editingDraftId ? "/drafts/" + encodeURIComponent(state.editingDraftId) : "/drafts";
    const method = state.editingDraftId ? "PUT" : "POST";
    await request(orgPath("/mailboxes/" + encodeURIComponent(mailboxId) + suffix), {
      method:method,
      body:JSON.stringify(payload)
    });
    state.mailboxId = mailboxId;
    closeCompose();
    state.view = "drafts";
    await loadWorkspace();
    renderCurrentView();
    flash("Draft saved securely");
  } catch (error) { flash(error.message); }
}

$("#login-form").addEventListener("submit", async event => {
  event.preventDefault();
  setError("");
  try {
    const auth = await request("/auth/login", {
      method:"POST",
      body:JSON.stringify({email:$("#login-email").value, password:$("#login-password").value})
    });
    state.token = auth.access_token;
    sessionStorage.seldruneMailToken = state.token;
    await establishSession();
  } catch (error) { setError(error.message); }
});

$("#logout").addEventListener("click", logout);
$("#compose-open").addEventListener("click", () => openCompose());
$("#compose-close").addEventListener("click", closeCompose);
$("#compose-cancel").addEventListener("click", closeCompose);
$("#compose-form").addEventListener("submit", saveDraft);
document.querySelectorAll(".mail-nav button").forEach(button => {
  button.addEventListener("click", () => {
    state.view = button.dataset.view;
    renderCurrentView();
  });
});

if (state.token) {
  establishSession().catch(error => {
    logout();
    setError(error.message);
  });
}
