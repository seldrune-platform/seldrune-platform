(()=>{
const API='/api/v1';
const $=s=>document.querySelector(s);
let organizationId='';

async function request(path,options={}){
  const token=sessionStorage.seldruneToken||'';
  if(!token)throw new Error('NO_SESSION');
  const response=await fetch(`${API}${path}`,{
    ...options,
    headers:{
      'Content-Type':'application/json',
      Authorization:`Bearer ${token}`,
      ...(options.headers||{}),
    },
  });
  if(response.status===401)throw new Error('SESSION_EXPIRED');
  if(!response.ok){
    const body=await response.json().catch(()=>({}));
    throw new Error(body.detail||`Request failed (${response.status})`);
  }
  return response.json();
}

function money(value){
  return`$${Number(value||0).toLocaleString(undefined,{maximumFractionDigits:2})}`;
}
function pct(value){return`${Math.round(Number(value||0)*100)}%`;}
function clear(selector){const element=$(selector);element.replaceChildren();return element;}
function text(tag,value,className=''){
  const element=document.createElement(tag);
  element.textContent=value;
  if(className)element.className=className;
  return element;
}
function pair(label,value){
  const row=document.createElement('div');
  row.append(text('span',label),text('strong',value));
  return row;
}
function metric(label,value){
  const item=document.createElement('div');
  item.className='metric';
  item.append(text('small',label),text('strong',String(value)));
  return item;
}
function showMessage(message,kind='message'){
  const root=clear('#message');
  const box=text('div',message,kind);
  root.append(box);
}
function lifecycleLabel(state){
  return({
    unassigned:'No action created',
    awaiting_approval:'Awaiting owner approval',
    active:'Governed action active',
    succeeded_unresolved:'Action succeeded · priority still present',
    partial:'Action partially completed',
    failed:'Action failed · follow-up available',
    cancelled:'Action cancelled · follow-up available',
    resolved:'Resolved by current evidence',
  })[state]||state;
}
function memoryLabel(confidence){
  return({none:'No comparable outcome evidence',low:'Limited outcome evidence',medium:'Usable outcome pattern',high:'Repeated outcome pattern'})[confidence]||confidence;
}
function strategyLabel(mode){
  return({
    observe:'Observe only',
    baseline:'Baseline strategy',
    reuse:'Reuse with verification',
    adapt:'Adapt learned evidence',
    explore:'Explore alternative',
    recover:'Escalated recovery',
  })[mode]||mode;
}
function advisorySignalLabel(signal){
  return({
    not_applicable:'Not applicable',
    insufficient_evidence:'Insufficient evidence',
    mixed:'Mixed evidence',
    keep_selected:'Keep selected strategy',
    use_recommended:'Use recommended strategy',
  })[signal]||signal||'Not recorded';
}
function confidenceLabel(confidence){
  return({none:'none',low:'low',medium:'medium',high:'high'})[confidence]||confidence||'none';
}
function driftChangeLabel(change){
  return({
    strategy_evidence:'strategy evidence',
    selected_mode:'selected strategy',
    recommended_mode:'recommended strategy',
    advisory_signal:'advisory signal',
    advisory_confidence:'advisory confidence',
  })[change]||change;
}
function driftSnapshotLabel(snapshot){
  const value=snapshot||{};
  return `${advisorySignalLabel(value.advisory_signal)} · confidence `+
    `${confidenceLabel(value.advisory_confidence)} · selected `+
    `${strategyLabel(value.selected_mode)} · recommended `+
    `${strategyLabel(value.recommended_mode||'none')}`;
}

async function runPriorityAction(item,button){
  button.disabled=true;
  const original=button.textContent;
  button.textContent='Creating governed command…';
  try{
    const key=encodeURIComponent(item.key);
    await request(
      `/organizations/${organizationId}/executive-brief/actions/${key}`,
      {method:'POST'},
    );
    button.textContent='Command ready for review';
    showMessage(
      'Governed owner command created or reused. Review and approve it in Owner Console.',
      'success',
    );
    await load();
  }catch(error){
    button.disabled=false;
    button.textContent=original;
    showMessage(error.message,'message');
  }
}

async function reviewStrategy(item,decision,button){
  const recommendation=(item.strategy||{}).recommendation||{};
  const target=decision==='use_recommended'
    ?strategyLabel(recommendation.recommended_mode)
    :strategyLabel((item.strategy||{}).mode);
  const reason=window.prompt(`Why should Seldrune use ${target}?`);
  if(reason===null)return;
  const trimmed=reason.trim();
  if(trimmed.length<3){
    showMessage('Strategy review rationale must contain at least 3 characters.');
    return;
  }
  button.disabled=true;
  const original=button.textContent;
  button.textContent='Recording owner review…';
  try{
    const key=encodeURIComponent(item.key);
    await request(
      `/organizations/${organizationId}/executive-brief/strategy-reviews/${key}`,
      {
        method:'POST',
        body:JSON.stringify({decision,reason:trimmed}),
      },
    );
    showMessage('Owner strategy review recorded against the current evidence snapshot.','success');
    await load();
  }catch(error){
    button.disabled=false;
    button.textContent=original;
    showMessage(error.message,'message');
  }
}

function renderPriority(item){
  const root=document.createElement('div');
  root.className='priority';
  const escalation=item.escalation||{level:0};
  const severity=escalation.effective_severity||item.severity;
  const heading=document.createElement('h3');
  heading.append(
    text('span',severity,`severity ${severity}`),
    document.createTextNode(item.title),
  );
  root.append(heading,text('p',item.detail));

  const lifecycle=item.lifecycle||{state:'unassigned',attempts:0};
  root.append(
    text(
      'p',
      `${lifecycleLabel(lifecycle.state)} · ${lifecycle.attempts||0} attempt(s)`,
      `lifecycle lifecycle-${lifecycle.state}`,
    ),
  );
  if(escalation.level){
    root.append(
      text(
        'p',
        `Escalation level ${escalation.level} · `+
        `${escalation.completed_attempts} completed attempt(s) · `+
        `${escalation.reason||'alternate strategy required'}`,
        'escalation',
      ),
    );
  }

  const memory=item.outcome_memory||{};
  if((memory.resolution_patterns||0)||(memory.unsuccessful_patterns||0)){
    root.append(
      text(
        'p',
        `${memoryLabel(memory.confidence)} · `+
        `${memory.resolution_patterns||0} resolution-associated pattern(s) · `+
        `${memory.unsuccessful_patterns||0} unsuccessful pattern(s). `+
        'Associations are evidence, not proof of causation.',
        'outcome-memory',
      ),
    );
  }

  const strategy=item.strategy||{};
  if(strategy.mode){
    root.append(
      text(
        'p',
        `${strategyLabel(strategy.mode)} · ${strategy.rationale||''}`,
        'strategy',
      ),
    );
  }
  const score=strategy.outcome_score||{};
  if(score.family_attempts){
    root.append(
      text(
        'p',
        `Strategy evidence · family attempts ${score.family_attempts} · `+
        `${strategyLabel(strategy.mode)} attempts ${score.attempts||0} · `+
        `${Math.round(Number(score.resolution_rate||0)*100)}% resolution association. `+
        'Recorded association only; not proof of causation.',
        'outcome-memory',
      ),
    );
  }
  const recommendation=strategy.recommendation||{};
  const review=item.strategy_review||{};
  if(recommendation.recommended_mode){
    root.append(
      text(
        'p',
        `Advisory strategy recommendation · consider `+
        `${strategyLabel(recommendation.recommended_mode)} · `+
        `${recommendation.evidence_strength||'none'} evidence · `+
        `${recommendation.attempts||0} attempts · `+
        `${Math.round(Number(recommendation.resolution_rate||0)*100)}% `+
        'resolution association. Not auto-applied; owner review required.',
        'strategy',
      ),
    );
    if(review.current){
      root.append(
        text(
          'p',
          `Owner strategy review recorded · ${review.status} · effective mode `+
          `${strategyLabel(review.effective_mode)}.`,
          'outcome-memory',
        ),
      );
    }else if(review.status==='stale'){
      root.append(
        text(
          'p',
          'Previous owner strategy review is stale because the evidence changed. Review again '+
          'before creating a new governed command.',
          'escalation',
        ),
      );
      const drift=review.drift_explanation||{};
      if(drift.active){
        const changes=(drift.changes||[]).map(driftChangeLabel);
        if(changes.length){
          root.append(
            text(
              'p',
              `Review evidence changes · ${changes.join(' · ')}.`,
              'outcome-memory',
            ),
          );
        }
        root.append(
          text('p',`Reviewed snapshot · ${driftSnapshotLabel(drift.reviewed)}.`,'muted'),
          text('p',`Current snapshot · ${driftSnapshotLabel(drift.current)}.`,'muted'),
        );
      }
    }else{
      root.append(
        text(
          'p',
          'Owner strategy review is required before creating a new governed command.',
          'escalation',
        ),
      );
    }
  }

  const action=item.action||null;
  if(action){
    const controls=document.createElement('div');
    controls.className='priority-actions';
    if(action.kind==='navigate'&&action.href){
      const link=document.createElement('a');
      link.href=action.href;
      link.textContent=action.label||'Open';
      controls.append(link);
    }else if(action.kind==='owner_command'&&item.key){
      if(['awaiting_approval','active'].includes(lifecycle.state)){
        const link=document.createElement('a');
        link.href='/console';
        link.textContent='Open current governed command';
        controls.append(link);
      }else if(review.required&&!review.current){
        const keep=document.createElement('button');
        keep.type='button';
        keep.textContent=`Keep ${strategyLabel(strategy.mode)}`;
        keep.onclick=()=>reviewStrategy(item,'keep_selected',keep);
        controls.append(keep);

        const use=document.createElement('button');
        use.type='button';
        use.textContent=`Use ${strategyLabel(recommendation.recommended_mode)}`;
        use.onclick=()=>reviewStrategy(item,'use_recommended',use);
        controls.append(use);
      }else{
        const button=document.createElement('button');
        button.type='button';
        button.textContent=escalation.level
          ?'Create escalated follow-up'
          :(lifecycle.state==='unassigned'
            ?(action.label||'Create governed command')
            :'Create follow-up governed command');
        button.onclick=()=>runPriorityAction(item,button);
        controls.append(button);
      }
    }
    if(controls.childElementCount)root.append(controls);
  }
  return root;
}

function renderResolved(item){
  const root=document.createElement('div');
  root.className='resolved-action';
  root.append(
    text('h3',item.title),
    text(
      'p',
      `${lifecycleLabel(item.state)} · ${item.attempts} attempt(s) · `+
      `${item.completed_attempts||0} completed · last command ${item.latest_command_status}`,
    ),
  );
  return root;
}
function renderPlaybook(item){
  const root=document.createElement('div');
  root.className='playbook';
  const latest=item.latest||{};
  root.append(
    text('h3',item.family),
    text(
      'p',
      `${memoryLabel(item.confidence)} · ${item.resolution_patterns} `+
      `resolution-associated pattern(s) · reference command ${latest.command_id||'—'}`,
    ),
  );
  if(latest.objective){
    root.append(text('p',latest.objective,'muted'));
  }
  return root;
}
function renderIncident(item){
  const root=document.createElement('div');
  root.className='incident';
  root.append(text('h3',item.title),text('p',item.detail||item.type));
  return root;
}
function renderAgent(item){
  const root=document.createElement('div');
  root.className='agent';
  const rate=item.success_rate===null||item.success_rate===undefined
    ?'No completed evidence'
    :`${Math.round(item.success_rate*100)}% success`;
  root.append(
    text('h3',item.name),
    text(
      'p',
      `${item.succeeded_tasks} succeeded · ${rate} · `+
      `${money(item.estimated_cost_usd)} recorded cost`,
    ),
  );
  return root;
}

function render(data){
  $('#health-score').textContent=data.health.score;
  $('#health-posture').textContent=data.health.posture;
  const snapshot=data.operating_snapshot;
  const actions=data.executive_actions||{};
  const memory=data.outcome_memory||{};
  const strategy=data.executive_strategy||{};
  const reviews=data.executive_strategy_review||{};
  const outcomes=data.strategy_outcomes||{};
  const reviewOutcomes=data.strategy_review_outcomes||{};
  const reviewDrift=reviewOutcomes.review_drift||{};
  const metrics=clear('#metrics');
  [
    ['Open goals',snapshot.open_goals],
    ['Active projects',snapshot.active_projects],
    ['Awaiting approval',snapshot.commands_awaiting_approval],
    ['Tracked actions',actions.tracked_priorities||0],
    ['Escalated actions',actions.escalated_priorities||0],
    ['Learned families',memory.learned_families||0],
    ['Resolution patterns',memory.resolution_patterns||0],
    ['Unsuccessful patterns',memory.unsuccessful_patterns||0],
    ['Strategy-informed',strategy.history_informed_priorities||0],
    ['Strategy recommendations',strategy.comparative_recommendations||0],
    ['Strategy reviews',reviews.reviewed||0],
    ['Pending reviews',(reviews.pending||0)+(reviews.stale||0)],
    ['Stale review drift',reviewDrift.stale_reviews||0],
    ['Explained drift',reviewDrift.explained_stale_reviews||0],
    ['Strategy attempts',outcomes.scored_attempts||0],
    ['Verified resolutions',outcomes.verified_resolution_associations||0],
  ].forEach(item=>metrics.append(metric(item[0],item[1])));

  const priorities=clear('#priorities');
  if(data.priorities.length){
    data.priorities.forEach(item=>priorities.append(renderPriority(item)));
  }else{
    priorities.append(
      text('p','No immediate owner intervention is indicated by current evidence.','empty'),
    );
  }

  const playbooks=clear('#outcome-playbooks');
  if((data.outcome_playbooks||[]).length){
    data.outcome_playbooks.forEach(item=>playbooks.append(renderPlaybook(item)));
  }else{
    playbooks.append(
      text('p','No resolution-associated executive patterns have been learned yet.','empty'),
    );
  }

  const resolved=clear('#resolved-actions');
  if((data.resolved_actions||[]).length){
    data.resolved_actions.forEach(item=>resolved.append(renderResolved(item)));
  }else{
    resolved.append(text('p','No resolved executive actions recorded yet.','empty'));
  }

  const incidents=clear('#incidents');
  if(data.recent_incidents.length){
    data.recent_incidents.forEach(item=>incidents.append(renderIncident(item)));
  }else{
    incidents.append(text('p','No current operational incidents.','empty'));
  }

  const treasuryData=data.treasury;
  const treasury=clear('#treasury');
  treasury.append(
    pair('Allocated',money(treasuryData.allocated_budget_usd)),
    pair('Spent',money(treasuryData.spent_budget_usd)),
    pair('Reserved',money(treasuryData.reserved_budget_usd)),
    pair('Available',money(treasuryData.available_budget_usd)),
    pair('Utilization',pct(treasuryData.utilization)),
    pair('Overcommitted',treasuryData.overcommitted?'Yes':'No'),
  );

  const governanceData=data.governance;
  const governance=clear('#governance');
  governance.append(
    pair('Max command steps',governanceData.max_steps_per_command),
    pair('Max project budget',money(governanceData.max_project_budget_usd)),
    pair(
      'Autonomous execution',
      governanceData.allow_autonomous_execution?'Allowed':'Disabled',
    ),
  );

  const agents=clear('#agents');
  if(data.top_agents.length){
    data.top_agents.forEach(item=>agents.append(renderAgent(item)));
  }else{
    agents.append(text('p','No verified agent delivery evidence yet.','empty'));
  }
}

async function load(){
  clear('#message');
  try{
    const me=await request('/auth/me');
    const membership=me.memberships.find(item=>item.role==='owner');
    if(!membership)throw new Error('OWNER_REQUIRED');
    organizationId=membership.organization.id;
    const data=await request(`/organizations/${organizationId}/executive-brief`);
    render(data);
  }catch(error){
    if(['NO_SESSION','SESSION_EXPIRED'].includes(error.message)){
      showMessage(
        'Sign in to the Owner Console first, then open Executive Brief in the same browser tab.',
      );
    }else if(error.message==='OWNER_REQUIRED'){
      showMessage('Executive Brief requires an organization owner account.');
    }else{
      showMessage(error.message);
    }
  }
}

$('#refresh').onclick=load;
load();
})();