(() => {
  "use strict";
  const root = document.querySelector("[data-studio-board]");
  if (!root) return;
  const stage = root.querySelector("[data-board-stage]");
  const items = root.querySelector("[data-board-items]");
  const links = root.querySelector("[data-board-links]");
  const empty = root.querySelector("[data-board-empty]");
  const thesis = root.querySelector("[data-board-thesis]");
  const saveState = root.querySelector("[data-board-save-state]");
  const panel = root.querySelector("[data-board-intelligence]");
  const menu = root.querySelector("[data-connection-menu]");
  const csrf = root.querySelector("[data-board-csrf]")?.value || "";
  const labels = JSON.parse(root.dataset.labels || "{}");
  const copy = JSON.parse(root.dataset.copy || "{}");
  let board = JSON.parse(root.dataset.board || "{}");
  board.nodes = Array.isArray(board.nodes) ? board.nodes.map(node => {
    const base={id:node.id,kind:node.kind,x:node.x,y:node.y};
    if(node.kind==="story") return {...base,slug:node.slug};
    if(node.kind==="headline") return {...base,title:node.title,source:node.source,source_story:node.source_story};
    if(node.kind==="catalyst") return {...base,name:node.name,timing:node.timing,source_story:node.source_story};
    return base;
  }) : [];
  board.connections = Array.isArray(board.connections) ? board.connections : [];
  let saveTimer = 0, drag = null, linkSource = null, pendingTarget = null, clickSuppressed = false;

  const escapeHtml = value => String(value || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const uid = prefix => `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  const storyData = slug => {
    const rail = document.querySelector(`[data-board-story][data-story-slug="${CSS.escape(slug)}"]`);
    return {name: rail?.querySelector(".studio-rail-name")?.textContent?.trim() || slug, direction: [...(rail?.querySelector(".studio-rail-glyph")?.classList || [])].find(x => x.startsWith("direction-"))?.slice(10) || "steady", directionLabel:rail?.dataset.directionLabel || ""};
  };
  const scheduleSave = () => {
    if (!csrf) return;
    saveState.textContent = copy.save_saving;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 800);
  };
  const save = async () => {
    const body = new URLSearchParams({csrf_token: csrf, payload: JSON.stringify(board)});
    try {
      const response = await fetch(root.dataset.saveUrl, {method:"POST", headers:{"Content-Type":"application/x-www-form-urlencoded"}, body});
      if (!response.ok) throw new Error();
      saveState.textContent = copy.save_saved;
    } catch (_) { saveState.textContent = copy.save_error; }
  };
  const nodeEl = id => items.querySelector(`[data-item-id="${CSS.escape(id)}"]`);
  const center = node => ({x:node.x + 95, y:node.y + 48});
  const renderLinks = () => {
    links.querySelectorAll("g").forEach(el => el.remove());
    for (const connection of board.connections) {
      const source = board.nodes.find(n => n.id === connection.from), target = board.nodes.find(n => n.id === connection.to);
      if (!source || !target) continue;
      const a=center(source), b=center(target), ns="http://www.w3.org/2000/svg", group=document.createElementNS(ns,"g");
      group.dataset.connectionId=connection.id; group.classList.add(`connection-${connection.label}`);
      const line=document.createElementNS(ns,"line"); line.setAttribute("x1",a.x);line.setAttribute("y1",a.y);line.setAttribute("x2",b.x);line.setAttribute("y2",b.y);line.setAttribute("marker-end","url(#studioArrow)");
      const pill=document.createElementNS(ns,"text");pill.setAttribute("x",(a.x+b.x)/2);pill.setAttribute("y",(a.y+b.y)/2-6);pill.textContent=labels[connection.label]||connection.label;pill.setAttribute("tabindex","0");pill.setAttribute("role","button");pill.addEventListener("click",()=>{board.connections=board.connections.filter(c=>c.id!==connection.id);renderLinks();scheduleSave();});
      group.append(line,pill); links.append(group);
    }
  };
  const renderNode = node => {
    const article=document.createElement("article");
    article.style.left=`${node.x}px`;article.style.top=`${node.y}px`;article.dataset.boardItem="";article.dataset.itemId=node.id;article.dataset.itemKind=node.kind;article.tabIndex=0;
    if(node.kind==="story"){
      const data=storyData(node.slug);article.className=`studio-evidence direction-${data.direction}`;article.dataset.storySlug=node.slug;
      article.innerHTML=`<button type="button" class="studio-evidence-main" data-board-open><span class="studio-evidence-direction" aria-hidden="true">${data.direction==="up"?"▲":data.direction==="down"?"▼":"→"}</span><strong>${escapeHtml(data.name)}</strong><small>${escapeHtml(data.directionLabel)}</small></button><button type="button" class="studio-link-handle" data-board-link aria-label="${escapeHtml(copy.connect_evidence)}">＋</button><button type="button" class="studio-item-remove" data-board-remove aria-label="${escapeHtml(copy.remove_evidence)}">×</button>`;
    }else{
      const headline=node.kind==="headline",primary=headline?node.title:node.name,meta=headline?node.source:node.timing;
      article.className=`studio-evidence studio-evidence-leaf studio-evidence-${node.kind}`;
      article.innerHTML=`<div class="studio-evidence-main studio-evidence-leaf-main"><span class="studio-evidence-leaf-glyph" aria-hidden="true">${headline?'“':'◷'}</span><span class="studio-evidence-kind-label">${escapeHtml(headline?copy.headline_evidence:copy.catalyst_evidence)}</span><strong>${escapeHtml(primary)}</strong><small>${escapeHtml(meta)}</small></div><button type="button" class="studio-item-remove" data-board-remove aria-label="${escapeHtml(copy.remove_evidence)}">×</button>`;
    }
    items.append(article); bindNode(article); return article;
  };
  const clamp = (value, max) => Math.max(0, Math.min(max, Math.round(value)));
  const addAt = (slug, clientX, clientY) => {
    if (board.nodes.some(n=>n.slug===slug) || board.nodes.length>=40) return;
    const rect=stage.getBoundingClientRect(), node={id:uid("story"),kind:"story",slug,x:clamp(clientX-rect.left-95,stage.clientWidth-190),y:clamp(clientY-rect.top-48,stage.clientHeight-96)};
    board.nodes.push(node);renderNode(node);empty.classList.add("hidden");renderLinks();scheduleSave();
  };
  const evidenceExists = (kind, sourceStory, primary) => board.nodes.some(node=>node.kind===kind&&node.source_story===sourceStory&&(kind==="headline"?node.title:node.name)===primary);
  const refreshPromotionButtons = () => panel.querySelectorAll("[data-add-evidence]").forEach(button=>{
    const source=board.nodes.find(node=>node.kind==="story"&&node.slug===button.dataset.storySlug),kind=button.dataset.evidenceKind,primary=button.dataset.evidencePrimary;
    const added=Boolean(source&&evidenceExists(kind,source.id,primary));button.disabled=added;button.textContent=added?copy.evidence_added:`+ ${copy.evidence_add}`;
  });
  const promoteEvidence = (kind, data, slug) => {
    const source=board.nodes.find(node=>node.kind==="story"&&node.slug===slug),primary=kind==="headline"?data.title:data.name;
    if(!source||evidenceExists(kind,source.id,primary)||board.nodes.length>=40||board.connections.length>=80){refreshPromotionButtons();return;}
    const nearby=board.nodes.filter(node=>node.source_story===source.id).length;
    const node={id:uid(kind),kind,x:clamp(source.x+220,stage.clientWidth-190),y:clamp(source.y+nearby*112,stage.clientHeight-96),source_story:source.id,...data};
    board.nodes.push(node);board.connections.push({id:uid("link"),from:node.id,to:source.id,label:"supports"});renderNode(node);renderLinks();empty.classList.add("hidden");refreshPromotionButtons();scheduleSave();
  };
  const openPanel = async slug => {
    panel.innerHTML=`<span class="eyebrow">${copy.intelligence_loading}</span>`;
    try {
      const response=await fetch(root.dataset.intelligenceUrl+encodeURIComponent(slug)); if(!response.ok) throw new Error(); const data=await response.json();
      const sections=[];
      if(data.headlines?.length) sections.push(`<section><h3>${copy.intelligence_headlines}</h3><ul>${data.headlines.map((x,index)=>`<li>${escapeHtml(x.title)}${x.source?` <small>${escapeHtml(x.source)}</small>`:""}<button type="button" data-add-evidence data-evidence-kind="headline" data-evidence-index="${index}" data-evidence-primary="${escapeHtml(x.title)}" data-story-slug="${escapeHtml(slug)}">+ ${copy.evidence_add}</button></li>`).join("")}</ul></section>`);
      if(data.related?.length) sections.push(`<section><h3>${copy.intelligence_related}</h3><ul>${data.related.map(x=>`<li><strong>${escapeHtml(x.name)}</strong> · ${escapeHtml(x.label)}</li>`).join("")}</ul></section>`);
      if(data.catalyst) sections.push(`<section><h3>${copy.intelligence_catalyst}</h3><p>${escapeHtml(data.catalyst.name)} <small>${escapeHtml(data.catalyst.timing)}</small><button type="button" data-add-evidence data-evidence-kind="catalyst" data-evidence-primary="${escapeHtml(data.catalyst.name)}" data-story-slug="${escapeHtml(slug)}">+ ${copy.evidence_add}</button></p></section>`);
      const otherSlugs=new Set(board.nodes.filter(n=>n.slug!==slug).map(n=>n.slug)); const hint=data.relationship_hints?.find(h=>h.story_slugs?.some(s=>otherSlugs.has(s)));
      const targetSlug=hint?.story_slugs?.find(s=>otherSlugs.has(s));
      if(hint) sections.push(`<section class="studio-relationship-hint"><h3>${copy.relationship_title}</h3><strong>${escapeHtml(hint.label)}</strong><p>${escapeHtml(hint.explanation)}</p><button type="button" data-use-relationship data-source-slug="${escapeHtml(slug)}" data-target-slug="${escapeHtml(targetSlug)}">${copy.relationship_action}</button></section>`);
      panel.innerHTML=`<span class="eyebrow">${escapeHtml(data.direction_label)}</span><h2>${escapeHtml(data.story)}</h2>${sections.join("")||`<p>${escapeHtml(data.empty_message||copy.intelligence_empty)}</p>`}<a href="${escapeHtml(data.research_url)}">${copy.research_deep_dive}</a>`;
      panel.querySelectorAll("[data-add-evidence]").forEach(button=>button.addEventListener("click",()=>{const kind=button.dataset.evidenceKind,index=Number(button.dataset.evidenceIndex||0);promoteEvidence(kind,kind==="headline"?{title:data.headlines[index].title,source:data.headlines[index].source||""}:{name:data.catalyst.name,timing:data.catalyst.timing||""},slug);}));
      refreshPromotionButtons();
      panel.querySelector("[data-use-relationship]")?.addEventListener("click",event=>{const button=event.currentTarget,source=board.nodes.find(n=>n.slug===button.dataset.sourceSlug),target=board.nodes.find(n=>n.slug===button.dataset.targetSlug);if(!source||!target)return;linkSource=source.id;pendingTarget=target.id;nodeEl(source.id)?.classList.add("selected");menu.classList.remove("hidden");menu.style.left=`${target.x}px`;menu.style.top=`${target.y}px`;});
    } catch (_) { panel.innerHTML=`<p>${copy.intelligence_empty}</p>`; }
  };
  const bindNode = el => {
    el.querySelector("[data-board-open]")?.addEventListener("click",event=>{event.preventDefault();if(!clickSuppressed)openPanel(el.dataset.storySlug);clickSuppressed=false;});
    el.querySelector("[data-board-remove]").addEventListener("click",()=>{const id=el.dataset.itemId;board.nodes=board.nodes.filter(n=>n.id!==id);board.connections=board.connections.filter(c=>c.from!==id&&c.to!==id);el.remove();renderLinks();refreshPromotionButtons();empty.classList.toggle("hidden",board.nodes.length>0);scheduleSave();});
    el.querySelector("[data-board-link]")?.addEventListener("pointerdown",event=>{event.stopPropagation();linkSource=el.dataset.itemId;el.classList.add("selected");});
    el.addEventListener("pointerdown",event=>{if(event.target.closest("button,a"))return;const node=board.nodes.find(n=>n.id===el.dataset.itemId);drag={el,node,startX:event.clientX,startY:event.clientY,x:node.x,y:node.y};el.setPointerCapture(event.pointerId);});
    el.addEventListener("pointermove",event=>{if(!drag||drag.el!==el)return;const dx=event.clientX-drag.startX,dy=event.clientY-drag.startY;if(Math.abs(dx)+Math.abs(dy)>4)clickSuppressed=true;drag.node.x=clamp(drag.x+dx,stage.clientWidth-190);drag.node.y=clamp(drag.y+dy,stage.clientHeight-96);el.style.left=`${drag.node.x}px`;el.style.top=`${drag.node.y}px`;renderLinks();});
    el.addEventListener("pointerup",()=>{if(drag){drag=null;scheduleSave();}if(linkSource&&linkSource!==el.dataset.itemId){pendingTarget=el.dataset.itemId;menu.classList.remove("hidden");menu.style.left=el.style.left;menu.style.top=el.style.top;}});
  };
  document.querySelectorAll("[data-board-story]").forEach(el=>{el.addEventListener("pointerdown",event=>{const slug=el.dataset.storySlug,move=e=>{if(Math.abs(e.clientX-event.clientX)+Math.abs(e.clientY-event.clientY)>8)clickSuppressed=true;},up=e=>{document.removeEventListener("pointermove",move);document.removeEventListener("pointerup",up);const r=stage.getBoundingClientRect();if(e.clientX>=r.left&&e.clientX<=r.right&&e.clientY>=r.top&&e.clientY<=r.bottom)addAt(slug,e.clientX,e.clientY);};document.addEventListener("pointermove",move);document.addEventListener("pointerup",up);});});
  menu.querySelectorAll("[data-connection-label]").forEach(button=>button.addEventListener("click",()=>{if(linkSource&&pendingTarget&&board.connections.length<80){board.connections.push({id:uid("link"),from:linkSource,to:pendingTarget,label:button.dataset.connectionLabel});renderLinks();scheduleSave();}items.querySelectorAll(".selected").forEach(x=>x.classList.remove("selected"));linkSource=null;pendingTarget=null;menu.classList.add("hidden");}));
  items.querySelectorAll("[data-board-item]").forEach(bindNode);
  thesis?.addEventListener("input",()=>{board.thesis=thesis.value;scheduleSave();});
  renderLinks();
})();
