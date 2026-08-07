(function () {
  "use strict";
  var svg = document.getElementById("assetChart");
  var source = document.getElementById("asset-chart-data");
  var readout = document.getElementById("assetChartReadout");
  if (!svg || !source || !readout) return;
  var config;
  try { config = JSON.parse(source.textContent); } catch (error) { return; }
  if (!Array.isArray(config.candles) || !config.candles.length) return;

  var ranges = {"1M": 21, "3M": 63, "6M": 126};
  var width = 960, height = 440, left = 36, right = 142, top = 24, bottom = 42;
  var view = {bars: [], slot: 0, x0: left, min: 0, max: 0};
  var copy = config.copy || {};

  function number(value) {
    return Number(value).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }
  function labelDate(value) {
    var parts = String(value).split("-");
    return parts.length === 3 ? parts[1] + "/" + parts[2] : String(value);
  }
  function yFor(value) {
    return top + (view.max - value) / (view.max - view.min) * (height - top - bottom);
  }
  function line(x1, y1, x2, y2, attrs) {
    return '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '" ' + attrs + '></line>';
  }
  function render(range) {
    var bars = config.candles.slice(-ranges[range]);
    if (!bars.length) return;
    var recent = bars.slice(-20);
    var high20 = Math.max.apply(null, recent.map(function (bar) { return bar.high; }));
    var low20 = Math.min.apply(null, recent.map(function (bar) { return bar.low; }));
    var high = Math.max.apply(null, bars.map(function (bar) { return bar.high; }).concat([high20, config.launch]));
    var low = Math.min.apply(null, bars.map(function (bar) { return bar.low; }).concat([low20, config.launch]));
    var padding = Math.max((high - low) * 0.04, Math.abs(high || 1) * 0.005);
    view.bars = bars; view.max = high + padding; view.min = low - padding;
    view.slot = (width - left - right) / bars.length;
    var xRight = width - right;
    var bodyWidth = Math.max(1.5, view.slot * 0.62);
    var yHigh = yFor(high20), yLow = yFor(low20), parts = [];
    parts.push('<rect x="' + left + '" y="' + top + '" width="' + (xRight-left) + '" height="' + Math.max(0,yHigh-top) + '" fill="rgba(201,210,220,.04)"></rect>');
    parts.push('<rect x="' + left + '" y="' + yLow + '" width="' + (xRight-left) + '" height="' + Math.max(0,height-bottom-yLow) + '" fill="rgba(201,210,220,.04)"></rect>');
    bars.forEach(function (bar, index) {
      var cx = left + view.slot * (index + 0.5), up = bar.close >= bar.open;
      var color = up ? "#2dd4bf" : "#f16a5f";
      parts.push(line(cx, yFor(bar.high), cx, yFor(bar.low), 'stroke="' + color + '" stroke-opacity=".58" stroke-width="1"'));
      var yOpen = yFor(bar.open), yClose = yFor(bar.close);
      parts.push('<rect x="' + (cx-bodyWidth/2) + '" y="' + Math.min(yOpen,yClose) + '" width="' + bodyWidth + '" height="' + Math.max(.8,Math.abs(yOpen-yClose)) + '" rx=".6" fill="' + color + '"></rect>');
    });
    [[high20,yHigh,copy.rail_high,3],[low20,yLow,copy.rail_low,-5]].forEach(function (rail) {
      parts.push(line(left,rail[1],xRight,rail[1],'stroke="rgba(201,210,220,.45)" stroke-width="1"'));
      parts.push('<text x="' + (xRight+8) + '" y="' + (rail[1]+rail[3]) + '" fill="#8b95a3" font-size="11" font-family="ui-monospace,Menlo,monospace">' + rail[2] + ' ' + number(rail[0]) + '</text>');
    });
    var launchY = yFor(config.launch);
    parts.push(line(left,launchY,xRight,launchY,'stroke="#edf1f5" stroke-width="1.2" stroke-dasharray="5 4" stroke-opacity=".9"'));
    parts.push('<rect x="' + (xRight+6) + '" y="' + (launchY-11) + '" width="126" height="20" rx="6" fill="#171d25" stroke="rgba(255,255,255,.14)"></rect>');
    parts.push('<text x="' + (xRight+13) + '" y="' + (launchY+3) + '" fill="#edf1f5" font-size="11" font-family="ui-monospace,Menlo,monospace">' + copy.launch_line + ' ' + number(config.launch) + '</text>');
    var tickCount = Math.min(5,bars.length), used = {};
    for (var tick=0; tick<tickCount; tick++) {
      var barIndex = tickCount === 1 ? 0 : Math.round((bars.length-1)*tick/(tickCount-1));
      if (used[barIndex]) continue; used[barIndex] = true;
      var tx = left + view.slot * (barIndex+.5);
      parts.push('<text x="' + tx + '" y="' + (height-12) + '" fill="#8b95a3" font-size="10.5" text-anchor="middle" font-family="ui-monospace,Menlo,monospace">' + labelDate(bars[barIndex].date) + '</text>');
    }
    parts.push('<g id="assetCrosshair" style="display:none"><line id="assetCrosshairLine" y1="' + top + '" y2="' + (height-bottom) + '" stroke="rgba(230,236,242,.35)"></line></g>');
    svg.innerHTML = parts.join("");
    document.querySelectorAll(".range-btn").forEach(function (button) {
      if (button.dataset.range === range) button.setAttribute("aria-pressed","true");
      else button.removeAttribute("aria-pressed");
    });
  }
  function show(event) {
    var rect = svg.getBoundingClientRect(), vx = (event.clientX-rect.left)*width/rect.width;
    var index = Math.max(0,Math.min(view.bars.length-1,Math.floor((vx-left)/view.slot)));
    var bar = view.bars[index], cx = left + view.slot*(index+.5);
    var group = document.getElementById("assetCrosshair"), cross = document.getElementById("assetCrosshairLine");
    if (!bar || !group || !cross) return;
    group.style.display=""; cross.setAttribute("x1",cx); cross.setAttribute("x2",cx);
    var direction = bar.close >= bar.open ? "up" : "down";
    readout.innerHTML = '<div>' + bar.date + '</div>' + copy.open_short + ' ' + number(bar.open) + '  ' + copy.high_short + ' ' + number(bar.high) + '<br>' + copy.low_short + ' ' + number(bar.low) + '  <span class="' + direction + '">' + copy.close_short + ' ' + number(bar.close) + '</span>';
    readout.style.display="block";
  }
  function hide() {
    readout.style.display="none";
    var group=document.getElementById("assetCrosshair"); if(group) group.style.display="none";
  }
  svg.addEventListener("pointermove",show); svg.addEventListener("pointerleave",hide);
  document.querySelectorAll(".range-btn").forEach(function (button) { button.addEventListener("click",function(){hide();render(button.dataset.range);}); });
  render("3M");
}());
