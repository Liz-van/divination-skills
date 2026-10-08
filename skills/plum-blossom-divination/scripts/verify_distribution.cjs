#!/usr/bin/env node
/**
 * 吉凶分布验证：模拟全字库起卦，统计体用生克 verdict 分布
 * 验收标准（对比修复前）：方式B' 大吉 <45%、纯凶 >10%、整体大吉 ~35-45%
 */
const fs = require('fs');
const path = require('path');
const strokeData = JSON.parse(fs.readFileSync(path.join(__dirname, 'stroke_data.json'), 'utf8'));
const charStructure = JSON.parse(fs.readFileSync(path.join(__dirname, 'char_structure.json'), 'utf8'));
const strokeDirection = JSON.parse(fs.readFileSync(path.join(__dirname, 'stroke_direction.json'), 'utf8'));

const ELEM = { 1: '金', 2: '金', 3: '火', 4: '木', 5: '木', 6: '水', 7: '土', 8: '土' };
const gen = { '木': '火', '火': '土', '土': '金', '金': '水', '水': '木' };
const ovr = { '木': '土', '土': '水', '水': '火', '火': '金', '金': '木' };

function relation(bodyE, useE) {
  if (bodyE === useE) return '比和·大吉';
  if (gen[bodyE] === useE) return '体生用·小凶';
  if (gen[useE] === bodyE) return '用生体·大吉';
  if (ovr[bodyE] === useE) return '体克用·中吉';
  if (ovr[useE] === bodyE) return '用克体·凶';
  return '?';
}

// 模拟各时辰（1-12）取平均分布
const byMethod = {};
let total = 0;
const all = {};

for (const hex of Object.keys(strokeData)) {
  const n = strokeData[hex];
  if (typeof n !== 'number' || n <= 1) continue;
  total++;
  const struct = charStructure[hex];
  const dir = strokeDirection[hex];
  let method;

  if (struct) {
    method = 'A结构拆解';
    const front = strokeData[struct.c1_hex] || 0;
    const back = Math.max(strokeData[struct.c2_hex] || 0, 1);
    const up = ((front - 1) % 8) + 1, lo = ((back - 1) % 8) + 1;
    const ml = ((n - 1) % 6) + 1;
    const body = ml >= 4 ? lo : up, use = ml >= 4 ? up : lo;
    add(method, relation(ELEM[body], ELEM[use]));
  } else if (dir) {
    method = 'C方向分阴阳';
    const up = dir.yang === 0 ? 8 : ((dir.yang - 1) % 8) + 1, lo = dir.yin === 0 ? 8 : ((dir.yin - 1) % 8) + 1;
    const ml = ((n - 1) % 6) + 1;
    const body = ml >= 4 ? lo : up, use = ml >= 4 ? up : lo;
    add(method, relation(ELEM[body], ELEM[use]));
  } else {
    // B' 笔画平分+时辰：对所有时辰(1-12)平均
    method = "B'平分+时辰";
    for (let shichen = 1; shichen <= 12; shichen++) {
      const front = Math.max(Math.floor(n / 2), 1);
      const back = Math.max(Math.ceil(n / 2), 1) + shichen;
      const up = ((front - 1) % 8) + 1, lo = ((back - 1) % 8) + 1;
      const ml = ((n + shichen - 1) % 6) + 1;
      const body = ml >= 4 ? lo : up, use = ml >= 4 ? up : lo;
      add(method, relation(ELEM[body], ELEM[use]));
    }
  }
}

function add(method, v) {
  if (!byMethod[method]) byMethod[method] = {};
  byMethod[method][v] = (byMethod[method][v] || 0) + 1;
  all[v] = (all[v] || 0) + 1;
}

function pct(o) {
  const s = Object.values(o).reduce((a, b) => a + b, 0);
  const out = {};
  for (const [k, v] of Object.entries(o)) out[k] = (100 * v / s).toFixed(1) + '%';
  return out;
}

console.log('=== 各方式吉凶分布（B\' 为12时辰平均）===');
for (const [m, o] of Object.entries(byMethod)) {
  const s = Object.values(o).reduce((a, b) => a + b, 0);
  console.log(m + ' (' + s + '例): ' + JSON.stringify(pct(o)));
}
console.log('\n=== 整体 ===');
console.log(JSON.stringify(pct(all), null, 1));

// 验收
function pos(o) { return (o['比和·大吉'] || 0) + (o['用生体·大吉'] || 0) + (o['体克用·中吉'] || 0); }
function neg(o) { return (o['体生用·小凶'] || 0) + (o['用克体·凶'] || 0); }
const b = byMethod["B'平分+时辰"];
const sB = Object.values(b).reduce((a, c) => a + c, 0);
console.log('\n=== 验收（方式B\'）===');
console.log('大吉占比:', ((100 * ((b['比和·大吉'] || 0) + (b['用生体·大吉'] || 0)) / sB)).toFixed(1) + '% (目标<45%)');
console.log('纯凶占比:', ((100 * (b['用克体·凶'] || 0) / sB)).toFixed(1) + '% (目标>10%)');
console.log('积极合计(大吉+中吉):', (100 * pos(b) / sB).toFixed(1) + '%');
console.log('消极合计(小凶+凶):', (100 * neg(b) / sB).toFixed(1) + '%');
