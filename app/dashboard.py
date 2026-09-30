"""Runtime dashboard computed from the same JSONL events as the lab contract."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from fastapi.responses import HTMLResponse


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"
router = APIRouter()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    fraction = position - lower
    return round(ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * fraction, 3)


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator * 100, 2) if denominator else None


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def dashboard_snapshot(now: datetime | None = None) -> dict[str, Any]:
    """Compute the six contract panels over the latest 60 UTC minute buckets."""
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    last_minute = current.replace(second=0, microsecond=0)
    first_minute = last_minute - timedelta(minutes=config["time_range_minutes"] - 1)
    minutes = [first_minute + timedelta(minutes=index) for index in range(config["time_range_minutes"])]
    buckets: dict[datetime, list[dict[str, Any]]] = {minute: [] for minute in minutes}
    source = REPO_ROOT / config["panels"][0]["source"]
    invalid_lines = 0

    if source.exists():
        with source.open(encoding="utf-8") as lines:
            for line in lines:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    invalid_lines += 1
                    continue
                if not isinstance(event, dict):
                    invalid_lines += 1
                    continue
                timestamp = _timestamp(event.get("ts"))
                if timestamp is None:
                    invalid_lines += 1
                elif first_minute <= timestamp <= current:
                    buckets[timestamp.replace(second=0, microsecond=0)].append(event)

    events = [event for minute in minutes for event in buckets[minute]]
    received = [event for event in events if event.get("event") == "request_received"]
    sent = [event for event in events if event.get("event") == "response_sent"]
    failed = [event for event in events if event.get("event") == "request_failed"]
    retrievals = [
        event for event in events
        if event.get("tool_name") == "retrieval" and isinstance(event.get("tool_success"), bool)
    ]
    latency = [value for event in sent if (value := _number(event.get("latency_ms"))) is not None]
    ttft = [value for event in sent if (value := _number(event.get("ttft_ms"))) is not None]
    costs = [value for event in sent if (value := _number(event.get("cost_usd"))) is not None]
    quality = [value for event in sent if (value := _number(event.get("quality_score"))) is not None]

    def values_of(rows: list[dict[str, Any]], field: str) -> list[float]:
        return [value for event in rows if (value := _number(event.get(field))) is not None]

    def minute_events(minute: datetime, name: str) -> list[dict[str, Any]]:
        return [event for event in buckets[minute] if event.get("event") == name]

    error_types: dict[str, int] = {}
    for event in failed:
        name = str(event.get("error_type") or "Unknown")
        error_types[name] = error_types.get(name, 0) + 1

    thresholds = {panel["id"]: panel["threshold"] for panel in config["panels"]}
    return {
        "title": config["title"],
        "source": config["panels"][0]["source"],
        "generated_at": current.isoformat(),
        "time_range_minutes": config["time_range_minutes"],
        "refresh_seconds": config["refresh_seconds"],
        "invalid_lines": invalid_lines,
        "labels": [minute.strftime("%H:%M") for minute in minutes],
        "thresholds": thresholds,
        "panels": {
            "latency": {
                "p50": _percentile(latency, 50), "p95": _percentile(latency, 95),
                "p99": _percentile(latency, 99), "ttft_p95": _percentile(ttft, 95),
                "per_minute_p95": [
                    _percentile(values_of(minute_events(minute, "response_sent"), "latency_ms"), 95)
                    for minute in minutes
                ],
            },
            "traffic": {
                "count": len(received),
                "per_minute": [len(minute_events(minute, "request_received")) for minute in minutes],
            },
            "errors": {
                "error_rate_pct": _ratio(len(failed), len(received)),
                "retrieval_success_rate_pct": _ratio(
                    sum(event["tool_success"] for event in retrievals), len(retrievals)
                ),
                "by_type": error_types,
                "per_minute_error_rate": [
                    _ratio(len(minute_events(minute, "request_failed")),
                           len(minute_events(minute, "request_received")))
                    for minute in minutes
                ],
            },
            "cost": {
                "total_usd": round(sum(costs), 6),
                "per_minute": [
                    round(sum(values_of(minute_events(minute, "response_sent"), "cost_usd")), 6)
                    for minute in minutes
                ],
            },
            "tokens": {
                "input_total": int(sum(values_of(sent, "tokens_in"))),
                "output_total": int(sum(values_of(sent, "tokens_out"))),
                "input_per_minute": [
                    sum(values_of(minute_events(minute, "response_sent"), "tokens_in"))
                    for minute in minutes
                ],
                "output_per_minute": [
                    sum(values_of(minute_events(minute, "response_sent"), "tokens_out"))
                    for minute in minutes
                ],
            },
            "quality": {
                "mean": round(sum(quality) / len(quality), 3) if quality else None,
                "per_minute": [
                    round(sum(scores) / len(scores), 3) if scores else None
                    for minute in minutes
                    for scores in [values_of(minute_events(minute, "response_sent"), "quality_score")]
                ],
            },
        },
    }


@router.get("/dashboard/data")
async def dashboard_data() -> dict[str, Any]:
    return dashboard_snapshot()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> str:
    return DASHBOARD_HTML


DASHBOARD_HTML = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Day 13 · LLMOps dashboard</title><style>
:root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#17324b;background:#f5f8fc}
*{box-sizing:border-box}body{margin:0}main{max-width:1200px;margin:auto;padding:28px}
header{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:24px}
h1{font-size:1.8rem;margin:0 0 8px}p{margin:0;color:#50667a}.meta{text-align:right;font-size:.9rem}
.notice{padding:12px 16px;margin-bottom:18px;background:#eaf3ff;border:1px solid #b7d5f8;border-radius:10px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.card{background:#fff;border:1px solid #d6e1ed;border-radius:14px;padding:20px;box-shadow:0 2px 8px #17324b0d}
.card h2{margin:0 0 12px;font-size:1.1rem}.value{font-size:1.6rem;font-weight:700;color:#123f70}
.detail{min-height:42px;margin:8px 0;color:#3d566d;font-size:.91rem;line-height:1.5}
.chart{width:100%;height:110px;background:#f7faff;border-radius:8px}.legend{font-size:.82rem;color:#52687d;margin-top:7px}
.threshold{font-size:.82rem;font-weight:600;color:#80531e;margin-top:10px}
@media(max-width:760px){header{display:block}.meta{text-align:left;margin-top:12px}.grid{grid-template-columns:1fr}}
</style></head><body><main><header><div><h1>Monitoring &amp; LLMOps</h1><p>Dashboard từ structured logs của API</p></div>
<p class="meta" id="meta">Đang tải dữ liệu…</p></header><div id="notice" class="notice" hidden></div>
<section class="grid">
<article class="card"><h2>Latency &amp; TTFT</h2><div class="value" id="latency-value">—</div><div class="detail" id="latency-detail"></div><svg class="chart" id="latency-chart"></svg><div class="legend">P95 latency theo phút · ms</div><div class="threshold" id="latency-threshold"></div></article>
<article class="card"><h2>Traffic</h2><div class="value" id="traffic-value">—</div><div class="detail" id="traffic-detail"></div><svg class="chart" id="traffic-chart"></svg><div class="legend">Số request theo phút</div><div class="threshold" id="traffic-threshold"></div></article>
<article class="card"><h2>Errors &amp; retrieval</h2><div class="value" id="errors-value">—</div><div class="detail" id="errors-detail"></div><svg class="chart" id="errors-chart"></svg><div class="legend">Error rate theo phút · %</div><div class="threshold" id="errors-threshold"></div></article>
<article class="card"><h2>Cost</h2><div class="value" id="cost-value">—</div><div class="detail" id="cost-detail"></div><svg class="chart" id="cost-chart"></svg><div class="legend">Cost theo phút · USD</div><div class="threshold" id="cost-threshold"></div></article>
<article class="card"><h2>Tokens</h2><div class="value" id="tokens-value">—</div><div class="detail" id="tokens-detail"></div><svg class="chart" id="tokens-chart"></svg><div class="legend">Input (xanh) / output (cam) theo phút · tokens</div><div class="threshold" id="tokens-threshold"></div></article>
<article class="card"><h2>Quality proxy</h2><div class="value" id="quality-value">—</div><div class="detail" id="quality-detail"></div><svg class="chart" id="quality-chart"></svg><div class="legend">Quality trung bình theo phút · điểm 0–1</div><div class="threshold" id="quality-threshold"></div></article>
</section></main><script>
const set=(id,value)=>{document.getElementById(id).textContent=value};
const fmt=(value,digits=2)=>value==null?'Chưa có dữ liệu':Number(value).toFixed(digits);
function chart(id,series,threshold=null){
  const svg=document.getElementById(id), width=500,height=110,pad=12;
  svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.replaceChildren();
  const values=series.flat().filter(v=>v!=null&&Number.isFinite(Number(v))).map(Number);
  const max=Math.max(1,...values,threshold==null?0:Number(threshold))*1.1;
  const add=(tag,attributes)=>{const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attributes))node.setAttribute(k,v);svg.appendChild(node)};
  if(threshold!=null){const y=height-pad-Number(threshold)/max*(height-2*pad);add('line',{x1:pad,x2:width-pad,y1:y,y2:y,stroke:'#c08029','stroke-dasharray':'5 4','stroke-width':1.5})}
  series.forEach((data,index)=>{let segment=[];const color=index?'#d2752d':'#1577be';
    const flush=()=>{if(segment.length>1)add('polyline',{points:segment.join(' '),fill:'none',stroke:color,'stroke-width':2.5});else if(segment.length===1){const [cx,cy]=segment[0].split(',');add('circle',{cx,cy,r:3,fill:color})}segment=[]};
    data.forEach((value,i)=>{if(value==null){flush();return}const x=pad+i*(width-2*pad)/Math.max(1,data.length-1);const y=height-pad-Number(value)/max*(height-2*pad);segment.push(`${x},${y}`)});flush();
  });
}
async function load(){try{const response=await fetch('/dashboard/data',{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);const data=await response.json();const p=data.panels,t=data.thresholds;
  set('meta',`${data.time_range_minutes} phút gần nhất · làm mới mỗi ${data.refresh_seconds}s · ${data.source}\nCập nhật: ${new Date(data.generated_at).toLocaleString('vi-VN')}`);
  const notice=document.getElementById('notice');notice.hidden=p.traffic.count>0&&data.invalid_lines===0;notice.textContent=p.traffic.count===0?'Không có request trong 60 phút gần nhất. Chạy scripts/load_test.py để tạo dữ liệu.':`${data.invalid_lines} dòng log không hợp lệ đã được bỏ qua.`;
  set('latency-value',`${fmt(p.latency.p95)} ms P95`);set('latency-detail',`P50 ${fmt(p.latency.p50)} · P99 ${fmt(p.latency.p99)} · TTFT P95 ${fmt(p.latency.ttft_p95)} ms`);chart('latency-chart',[p.latency.per_minute_p95],t.latency.value);
  set('traffic-value',`${p.traffic.count} requests`);set('traffic-detail',`Cửa sổ ${data.time_range_minutes} phút · đơn vị requests/phút`);chart('traffic-chart',[p.traffic.per_minute],t.traffic.value);
  set('errors-value',`${fmt(p.errors.error_rate_pct)}% lỗi`);set('errors-detail',`Retrieval success: ${fmt(p.errors.retrieval_success_rate_pct)}% · lỗi theo loại: ${JSON.stringify(p.errors.by_type)}`);chart('errors-chart',[p.errors.per_minute_error_rate],t.errors.value);
  set('cost-value',`$${fmt(p.cost.total_usd,6)}`);set('cost-detail','Tổng USD trong cửa sổ; biểu đồ thể hiện USD/phút');chart('cost-chart',[p.cost.per_minute]);
  set('tokens-value',`${p.tokens.input_total+p.tokens.output_total} tokens`);set('tokens-detail',`Input ${p.tokens.input_total} · output ${p.tokens.output_total}`);chart('tokens-chart',[p.tokens.input_per_minute,p.tokens.output_per_minute]);
  set('quality-value',`${fmt(p.quality.mean,3)} / 1`);set('quality-detail','Trung bình quality_score trong cửa sổ');chart('quality-chart',[p.quality.per_minute],t.quality.value);
  for(const id of ['latency','traffic','errors','cost','tokens','quality']){const v=t[id];set(`${id}-threshold`,`Ngưỡng: ${v.aggregation} ${v.operator==='lte'?'≤':'≥'} ${v.value} ${id==='latency'?'ms':id==='cost'?'USD':id==='tokens'?'tokens':id==='quality'?'điểm':id==='traffic'?'requests/phút':'%'}`)}
}catch(error){const notice=document.getElementById('notice');notice.hidden=false;notice.textContent=`Không tải được dữ liệu dashboard: ${error.message}`}}
load();setInterval(load,30000);
</script></body></html>"""
