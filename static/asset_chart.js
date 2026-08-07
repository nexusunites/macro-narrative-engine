(function () {
  "use strict";
  var svg = document.getElementById("assetChart"), source = document.getElementById("asset-chart-data");
  var readout = document.getElementById("assetChartReadout"), chartMain = document.getElementById("chartMain");
  var panel = document.getElementById("assetEventPanel"), panelBody = document.getElementById("assetEventPanelBody");
  if (!svg || !source || !readout) return;
  var config;
  try { config = JSON.parse(source.textContent); } catch (error) { return; }
  if (!Array.isArray(config.candles) || !config.candles.length) return;

  var ranges = {"1M": 21, "3M": 63, "6M": 126};
  var width = 960, height = 440, left = 36, right = 142, top = 24, bottom = 42;
  var view = {bars: [], slot: 0, min: 0, max: 0, range: "3M", filter: "all", events: {}};
  var copy = config.copy || {}, allEvents = Array.isArray(config.events) ? config.events : [];
  function esc(value) { return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) { return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]; }); }
  function number(value) { return Number(value).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}); }
  function labelDate(value) { var parts=String(value).split("-"); return parts.length===3 ? parts[1]+"/"+parts[2] : String(value); }
  function yFor(value) { return top+(view.max-value)/(view.max-view.min)*(height-top-bottom); }
  function line(x1,y1,x2,y2,attrs) { return '<line x1="'+x1+'" y1="'+y1+'" x2="'+x2+'" y2="'+y2+'" '+attrs+'></line>'; }
  function visibleEvents() {
    if (view.filter === "hide") return [];
    return allEvents.filter(function (event) { return view.filter === "all" || event.type === view.filter; });
  }
  function eventsByDate(events) {
    return events.reduce(function (grouped,event) { (grouped[event.date]||(grouped[event.date]=[])).push(event); return grouped; },{});
  }
  function render(range) {
    view.range=range; var bars=config.candles.slice(-ranges[range]); if(!bars.length)return;
    var recent=bars.slice(-20), high20=Math.max.apply(null,recent.map(function(bar){return bar.high;}));
    var low20=Math.min.apply(null,recent.map(function(bar){return bar.low;}));
    var high=Math.max.apply(null,bars.map(function(bar){return bar.high;}).concat([high20,config.launch]));
    var low=Math.min.apply(null,bars.map(function(bar){return bar.low;}).concat([low20,config.launch]));
    var padding=Math.max((high-low)*.04,Math.abs(high||1)*.005); view.bars=bars;view.max=high+padding;view.min=low-padding;
    view.slot=(width-left-right)/bars.length; var xRight=width-right, bodyWidth=Math.max(1.5,view.slot*.62);
    var yHigh=yFor(high20),yLow=yFor(low20),parts=[]; view.events=eventsByDate(visibleEvents());
    parts.push('<rect x="'+left+'" y="'+top+'" width="'+(xRight-left)+'" height="'+Math.max(0,yHigh-top)+'" fill="rgba(201,210,220,.04)"></rect>');
    parts.push('<rect x="'+left+'" y="'+yLow+'" width="'+(xRight-left)+'" height="'+Math.max(0,height-bottom-yLow)+'" fill="rgba(201,210,220,.04)"></rect>');
    bars.forEach(function(bar,index){var cx=left+view.slot*(index+.5),up=bar.close>=bar.open,color=up?"#2dd4bf":"#f16a5f";
      parts.push(line(cx,yFor(bar.high),cx,yFor(bar.low),'stroke="'+color+'" stroke-opacity=".58" stroke-width="1"'));
      var yOpen=yFor(bar.open),yClose=yFor(bar.close);parts.push('<rect x="'+(cx-bodyWidth/2)+'" y="'+Math.min(yOpen,yClose)+'" width="'+bodyWidth+'" height="'+Math.max(.8,Math.abs(yOpen-yClose))+'" rx=".6" fill="'+color+'"></rect>');
    });
    [[high20,yHigh,copy.rail_high,3],[low20,yLow,copy.rail_low,-5]].forEach(function(rail){parts.push(line(left,rail[1],xRight,rail[1],'stroke="rgba(201,210,220,.45)" stroke-width="1"'));parts.push('<text x="'+(xRight+8)+'" y="'+(rail[1]+rail[3])+'" fill="#8b95a3" font-size="11" font-family="ui-monospace,Menlo,monospace">'+esc(rail[2])+' '+number(rail[0])+'</text>');});
    var launchY=yFor(config.launch);parts.push(line(left,launchY,xRight,launchY,'stroke="#edf1f5" stroke-width="1.2" stroke-dasharray="5 4" stroke-opacity=".9"'));
    parts.push('<rect x="'+(xRight+6)+'" y="'+(launchY-11)+'" width="126" height="20" rx="6" fill="#171d25" stroke="rgba(255,255,255,.14)"></rect><text x="'+(xRight+13)+'" y="'+(launchY+3)+'" fill="#edf1f5" font-size="11" font-family="ui-monospace,Menlo,monospace">'+esc(copy.launch_line)+' '+number(config.launch)+'</text>');
    bars.forEach(function(bar,index){var events=view.events[bar.date];if(!events||!events.length)return;var cx=left+view.slot*(index+.5),above=yFor(bar.high)-18;
      var flipped=above<top+14||Math.abs(above-yHigh)<18,cy=flipped?yFor(bar.low)+18:above,glyph=events.length>1?events.length:(events[0].type==="earnings"?"E":(events[0].type==="news"?"N":"M"));
      parts.push('<g class="asset-event-marker" data-event-date="'+esc(bar.date)+'" role="button" tabindex="0" aria-label="'+events.length+' '+esc(events.length===1?events[0].title:"events")+'"><circle cx="'+cx+'" cy="'+cy+'" r="10" fill="#171d25" stroke="#8b95a3" stroke-width="1.5"></circle><text x="'+cx+'" y="'+(cy+3.5)+'" text-anchor="middle" fill="#b9c2cd" font-size="10" font-family="ui-monospace,Menlo,monospace">'+glyph+'</text></g>');
    });
    var tickCount=Math.min(5,bars.length),used={};for(var tick=0;tick<tickCount;tick++){var barIndex=tickCount===1?0:Math.round((bars.length-1)*tick/(tickCount-1));if(used[barIndex])continue;used[barIndex]=true;var tx=left+view.slot*(barIndex+.5);parts.push('<text x="'+tx+'" y="'+(height-12)+'" fill="#8b95a3" font-size="10.5" text-anchor="middle" font-family="ui-monospace,Menlo,monospace">'+labelDate(bars[barIndex].date)+'</text>');}
    parts.push('<g id="assetCrosshair" pointer-events="none" style="display:none"><line id="assetCrosshairLine" y1="'+top+'" y2="'+(height-bottom)+'" stroke="rgba(230,236,242,.35)"></line></g>');svg.innerHTML=parts.join("");
    document.querySelectorAll(".range-btn").forEach(function(button){button.setAttribute("aria-pressed",button.dataset.range===range?"true":"false");});
  }
  function show(event){var rect=svg.getBoundingClientRect(),vx=(event.clientX-rect.left)*width/rect.width,index=Math.max(0,Math.min(view.bars.length-1,Math.floor((vx-left)/view.slot)));
    var bar=view.bars[index],cx=left+view.slot*(index+.5),group=document.getElementById("assetCrosshair"),cross=document.getElementById("assetCrosshairLine");if(!bar||!group||!cross)return;group.style.display="";cross.setAttribute("x1",cx);cross.setAttribute("x2",cx);
    var direction=bar.close>=bar.open?"up":"down",html='<div>'+esc(bar.date)+'</div>'+esc(copy.open_short)+' '+number(bar.open)+'  '+esc(copy.high_short)+' '+number(bar.high)+'<br>'+esc(copy.low_short)+' '+number(bar.low)+'  <span class="'+direction+'">'+esc(copy.close_short)+' '+number(bar.close)+'</span>';
    (view.events[bar.date]||[]).forEach(function(item){html+='<div class="readout-event"><span class="event-type">'+esc(item.type)+'</span><br><strong>'+esc(item.title)+'</strong><br>'+esc(item.blurb)+'</div>';});readout.innerHTML=html;readout.style.display="block";
  }
  function hide(){readout.style.display="none";var group=document.getElementById("assetCrosshair");if(group)group.style.display="none";}
  function openPanel(eventDate){var events=view.events[eventDate]||[];if(!events.length||!panel||!panelBody)return;panelBody.innerHTML=events.map(function(item){var filingLink=item.url?' · <a href="'+esc(item.url)+'" target="_blank" rel="noopener">'+esc(copy.view_filing)+'</a>':'';return '<article><span class="event-type">'+esc(item.type)+' · '+esc(item.date)+'</span><h3>'+esc(item.title)+'</h3><p>'+esc(item.blurb)+'</p><p>'+esc(item.detail)+'</p><p><span class="execution-label">'+esc(copy.event_source)+'</span><br>'+esc(item.source)+filingLink+'</p></article>';}).join("");panel.hidden=false;if(chartMain)chartMain.classList.add("has-panel");}
  function closePanel(){if(panel)panel.hidden=true;if(chartMain)chartMain.classList.remove("has-panel");}
  svg.addEventListener("pointermove",show);svg.addEventListener("pointerleave",hide);svg.addEventListener("click",function(event){var marker=event.target.closest(".asset-event-marker");if(marker)openPanel(marker.dataset.eventDate);});
  svg.addEventListener("keydown",function(event){if((event.key==="Enter"||event.key===" ")&&event.target.classList.contains("asset-event-marker")){event.preventDefault();openPanel(event.target.dataset.eventDate);}});
  document.querySelectorAll(".range-btn").forEach(function(button){button.addEventListener("click",function(){hide();render(button.dataset.range);});});
  document.querySelectorAll(".event-filter-btn").forEach(function(button){button.addEventListener("click",function(){view.filter=button.dataset.eventFilter;document.querySelectorAll(".event-filter-btn").forEach(function(item){item.setAttribute("aria-pressed",item===button?"true":"false");});closePanel();hide();render(view.range);});});
  var closeButton=document.getElementById("assetEventClose");if(closeButton)closeButton.addEventListener("click",closePanel);document.addEventListener("keydown",function(event){if(event.key==="Escape")closePanel();});
  function updateCountdowns(){document.querySelectorAll("[data-scheduled-at]").forEach(function(card){var target=Date.parse(card.dataset.scheduledAt),node=card.querySelector("[data-countdown]");if(!node||!Number.isFinite(target))return;var delta=target-Date.now();if(delta<=0){node.textContent=copy.today_countdown;return;}var hours=Math.floor(delta/3600000),days=Math.floor(hours/24);node.textContent=days?days+"d "+(hours%24)+"h":hours+"h "+Math.floor((delta%3600000)/60000)+"m";});}
  render("3M");updateCountdowns();window.setInterval(updateCountdowns,60000);
}());
