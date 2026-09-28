(() => {
  const q = selector => document.querySelector(selector);
  const token = sessionStorage.getItem('seldruneToken') || '';
  const state = {organizationId: '', userId: '', canManage: false};

  const api = async (path, options = {}) => {
    const response = await fetch('/api/v1' + path, {
      ...options,
      headers: {
        Accept: 'application/json',
        ...(options.body ? {'Content-Type': 'application/json'} : {}),
        ...(token ? {Authorization: 'Bearer ' + token} : {}),
      },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || 'Request failed (' + response.status + ')');
    }
    return response.status === 204 ? null : response.json();
  };

  function setStatus(message, kind) {
    const element = q('#page-status');
    element.textContent = message;
    element.className = 'status-message' + (kind ? ' ' + kind : '');
  }

  function element(tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = value;
    return node;
  }

  function addButton(parent, label, className, action) {
    const button = element('button', 'button ' + className, label);
    button.type = 'button';
    button.addEventListener('click', action);
    parent.appendChild(button);
  }

  async function reviewGrant(grant, decision) {
    if (decision === 'approve') {
      const confirmed = window.confirm(
        'Confirm that you opened the referenced record, checked its SHA-256, and independently verified the subject consent? This approval is audited and cannot be edited.'
      );
      if (!confirmed) return;
    } else if (!window.confirm('Reject this profile authorization request?')) {
      return;
    }
    await api(
      '/organizations/' + state.organizationId + '/liveshift/profile-authorizations/' +
        encodeURIComponent(grant.id) + '/review',
      {
        method: 'POST',
        body: JSON.stringify({
          decision,
          evidence_reviewed: decision === 'approve',
          subject_consent_verified: decision === 'approve',
        }),
      },
    );
    await refresh();
    setStatus(decision === 'approve' ? 'Profile grant approved and audited.' : 'Profile request rejected.', 'success');
  }

  async function revokeGrant(grant) {
    if (!window.confirm('Revoke this profile grant? New live sessions will be denied.')) return;
    await api(
      '/organizations/' + state.organizationId + '/liveshift/profile-authorizations/' +
        encodeURIComponent(grant.id),
      {method: 'DELETE'},
    );
    await refresh();
    setStatus('Profile authorization revoked.', 'success');
  }

  function renderGrant(grant) {
    const card = element('article', 'grant-card');
    const heading = element('div', 'grant-heading');
    const title = element('h3', '', grant.profile_kind.toUpperCase() + ' · ' + grant.profile_id);
    const badge = element('span', 'status-pill ' + grant.status, grant.status.toUpperCase());
    heading.append(title, badge);
    card.appendChild(heading);
    card.appendChild(element('p', 'grant-detail', 'User: ' + grant.user_id));
    card.appendChild(element('p', 'grant-detail', 'Evidence reference: ' + grant.evidence_reference));
    card.appendChild(element('p', 'grant-detail mono', 'SHA-256: ' + grant.evidence_sha256));
    card.appendChild(element('p', 'grant-detail', 'Expires: ' + new Date(grant.expires_at).toLocaleDateString()));
    if (grant.reviewed_by_user_id) {
      card.appendChild(element('p', 'grant-detail', 'Reviewed by: ' + grant.reviewed_by_user_id));
    }
    const actions = element('div', 'action-row');
    if (grant.status === 'pending' && state.canManage && grant.requested_by_user_id !== state.userId) {
      addButton(actions, 'Approve after evidence review', 'primary', () => reviewGrant(grant, 'approve'));
      addButton(actions, 'Reject', 'secondary', () => reviewGrant(grant, 'reject'));
    }
    if (
      (grant.status === 'pending' || grant.status === 'approved') &&
      (grant.user_id === state.userId || state.canManage)
    ) {
      addButton(actions, 'Revoke', 'danger', () => revokeGrant(grant));
    }
    if (actions.childNodes.length) card.appendChild(actions);
    return card;
  }

  async function refresh() {
    if (!state.organizationId) return;
    const grants = await api(
      '/organizations/' + state.organizationId + '/liveshift/profile-authorizations',
    );
    const list = q('#grant-list');
    list.replaceChildren();
    if (!grants.length) {
      list.appendChild(element('p', 'empty-state', 'No profile requests or grants yet.'));
      return;
    }
    grants.forEach(grant => list.appendChild(renderGrant(grant)));
  }

  async function initialize() {
    if (!token) {
      setStatus('Sign in through the Seldrune console, then reopen this page.', 'error');
      q('#request-form').querySelector('button').disabled = true;
      return;
    }
    try {
      const me = await api('/auth/me');
      state.userId = me.user.id;
      if (!me.memberships.length) throw new Error('No Seldrune organization is available.');
      const select = q('#organization');
      const memberships = me.memberships;
      memberships.forEach(membership => {
        const option = element(
          'option',
          '',
          membership.organization.name + ' · ' + membership.role,
        );
        option.value = membership.organization.id;
        option.dataset.role = membership.role;
        select.appendChild(option);
      });
      const preferred = memberships.find(item => item.role === 'owner') || memberships[0];
      select.value = preferred.organization.id;
      await selectOrganization(preferred);
      select.addEventListener('change', async () => {
        const membership = memberships.find(item => item.organization.id === select.value);
        if (membership) await selectOrganization(membership);
      });
      q('#refresh-button').addEventListener('click', () => refresh().catch(error => setStatus(error.message, 'error')));
    } catch (error) {
      setStatus(error.message, 'error');
      q('#request-form').querySelector('button').disabled = true;
    }
  }

  async function selectOrganization(membership) {
    state.organizationId = membership.organization.id;
    state.canManage = membership.role === 'owner' || membership.role === 'admin';
    await refresh();
    setStatus(
      state.canManage
        ? 'Owner/admin view: review pending requests only after checking the external evidence record.'
        : 'Requests are visible to organization managers; only approved current grants can start a live session.',
      'success',
    );
  }

  q('#request-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (!state.organizationId) return;
    const date = q('#expires-at').value;
    if (!date) return;
    const expiresAt = new Date(date + 'T23:59:59').toISOString();
    try {
      await api(
        '/organizations/' + state.organizationId + '/liveshift/profile-authorizations',
        {
          method: 'POST',
          body: JSON.stringify({
            profile_kind: q('#profile-kind').value,
            profile_id: q('#profile-id').value.trim(),
            evidence_reference: q('#evidence-reference').value.trim(),
            evidence_sha256: q('#evidence-sha256').value.trim().toLowerCase(),
            expires_at: expiresAt,
          }),
        },
      );
      q('#request-form').reset();
      setStatus('Request submitted. The profile remains blocked until a different owner/admin reviews it.', 'success');
      await refresh();
    } catch (error) {
      setStatus(error.message, 'error');
    }
  });

  const defaultExpiry = new Date();
  defaultExpiry.setDate(defaultExpiry.getDate() + 180);
  q('#expires-at').value = defaultExpiry.toISOString().slice(0, 10);
  initialize();
})();
