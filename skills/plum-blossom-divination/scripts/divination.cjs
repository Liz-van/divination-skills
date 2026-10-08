#!/usr/bin/env node
/**
 * 梅花易数起卦计算脚本 v2（对齐《梅花易数断卦方法》全书）
 *
 * 用法：
 *   node divination.cjs <主题>            → 时辰占（年月日时起卦）
 *   node divination.cjs <主题> <数字...>  → 数字占（数字以空格分隔，个数不定）
 *   node divination.cjs <主题> <字>       → 一字占（结构拆解 → 笔画方向分阴阳 → 笔画平分+时辰数）
 *   node divination.cjs <主题> <字串>     → 多字占（2字按笔画；3字以上按字数，停匀平分/不匀上少下多）
 *   node divination.cjs <主题> --object <上卦名|数> <下卦名|数|方位> [动爻]  → 物象占
 *
 * 输出 JSON：本卦 / 互卦 / 变卦 / 体用生克 / 卦气旺衰
 */
const fs = require('fs');
const path = require('path');
const strokeData = JSON.parse(fs.readFileSync(path.join(__dirname, 'stroke_data.json'), 'utf8'));
const charStructure = JSON.parse(fs.readFileSync(path.join(__dirname, 'char_structure.json'), 'utf8'));
let strokeDirection = {};
try {
  strokeDirection = JSON.parse(fs.readFileSync(path.join(__dirname, 'stroke_direction.json'), 'utf8'));
} catch (e) { /* 方向表缺失时退化到笔画平分 */ }
const solar = require('./vendor/solarlunar.cjs').default;

// ── 八卦定义（先天卦数：乾1 兑2 离3 震4 巽5 坎6 艮7 坤8）──
const TRIGRAMS = {
  1: { num: 1, name: '乾', symbol: '☰', element: '金', nature: '天', character: '健', direction: '西北', season: '秋冬间', color: '白', family: '父', body: '首', animal: '马' },
  2: { num: 2, name: '兑', symbol: '☱', element: '金', nature: '泽', character: '悦', direction: '西',  season: '秋',   color: '白', family: '少女', body: '口', animal: '羊' },
  3: { num: 3, name: '离', symbol: '☲', element: '火', nature: '火', character: '丽', direction: '南',  season: '夏',   color: '赤', family: '中女', body: '目', animal: '雉' },
  4: { num: 4, name: '震', symbol: '☳', element: '木', nature: '雷', character: '动', direction: '东',  season: '春',   color: '苍', family: '长男', body: '足', animal: '龙' },
  5: { num: 5, name: '巽', symbol: '☴', element: '木', nature: '风', character: '入', direction: '东南',season: '春夏间',color: '青', family: '长女', body: '股', animal: '鸡' },
  6: { num: 6, name: '坎', symbol: '☵', element: '水', nature: '水', character: '陷', direction: '北',  season: '冬',   color: '黑', family: '中男', body: '耳', animal: '猪' },
  7: { num: 7, name: '艮', symbol: '☶', element: '土', nature: '山', character: '止', direction: '东北',season: '冬春间',color: '黄', family: '少男', body: '手', animal: '犬' },
  8: { num: 8, name: '坤', symbol: '☷', element: '土', nature: '地', character: '顺', direction: '西南',season: '夏秋间',color: '黄', family: '母', body: '腹', animal: '牛' },
};

// ── 六十四卦表 key: "上卦_下卦" ──
const HEXAGRAMS = {
  "1_1": { name: '乾为天',         number: 1,  judgment: '元，亨，利，贞。' },
  "1_2": { name: '天泽履',         number: 10, judgment: '履虎尾，不咥人，亨。' },
  "1_3": { name: '天火同人',       number: 13, judgment: '同人于野，亨。利涉大川，利君子贞。' },
  "1_4": { name: '天雷无妄',       number: 25, judgment: '元亨，利贞。其匪正有眚，不利有攸往。' },
  "1_5": { name: '天风姤',         number: 44, judgment: '女壮，勿用取女。' },
  "1_6": { name: '天水讼',         number: 6,  judgment: '有孚，窒惕，中吉，终凶。利见大人，不利涉大川。' },
  "1_7": { name: '天山遁',         number: 33, judgment: '亨，小利贞。' },
  "1_8": { name: '天地否',         number: 12, judgment: '否之匪人，不利君子贞，大往小来。' },
  "2_1": { name: '泽天夬',         number: 43, judgment: '扬于王庭，孚号有厉。告自邑，不利即戎，利有攸往。' },
  "2_2": { name: '兑为泽',         number: 58, judgment: '亨，利贞。' },
  "2_3": { name: '泽火革',         number: 49, judgment: '己日乃孚。元亨利贞，悔亡。' },
  "2_4": { name: '泽雷随',         number: 17, judgment: '元亨利贞，无咎。' },
  "2_5": { name: '泽风大过',       number: 28, judgment: '栋桡，利有攸往，亨。' },
  "2_6": { name: '泽水困',         number: 47, judgment: '亨，贞，大人吉，无咎。有言不信。' },
  "2_7": { name: '泽山咸',         number: 31, judgment: '亨，利贞，取女吉。' },
  "2_8": { name: '泽地萃',         number: 45, judgment: '亨。王假有庙，利见大人，亨，利贞。用大牲吉，利有攸往。' },
  "3_1": { name: '火天大有',       number: 14, judgment: '元亨。' },
  "3_2": { name: '火泽睽',         number: 38, judgment: '小事吉。' },
  "3_3": { name: '离为火',         number: 30, judgment: '利贞，亨。畜牝牛，吉。' },
  "3_4": { name: '火雷噬嗑',       number: 21, judgment: '亨，利用狱。' },
  "3_5": { name: '火风鼎',         number: 50, judgment: '元吉，亨。' },
  "3_6": { name: '火水未济',       number: 64, judgment: '亨。小狐汔济，濡其尾，无攸利。' },
  "3_7": { name: '火山旅',         number: 56, judgment: '小亨，旅贞吉。' },
  "3_8": { name: '火地晋',         number: 35, judgment: '康侯用锡马蕃庶，昼日三接。' },
  "4_1": { name: '雷天大壮',       number: 34, judgment: '利贞。' },
  "4_2": { name: '雷泽归妹',       number: 54, judgment: '征凶，无攸利。' },
  "4_3": { name: '雷火丰',         number: 55, judgment: '亨，王假之，勿忧，宜日中。' },
  "4_4": { name: '震为雷',         number: 51, judgment: '亨。震来虩虩，笑言哑哑。震惊百里，不丧匕鬯。' },
  "4_5": { name: '雷风恒',         number: 32, judgment: '亨，无咎，利贞，利有攸往。' },
  "4_6": { name: '雷水解',         number: 40, judgment: '利西南，无所往，其来复吉。有攸往，夙吉。' },
  "4_7": { name: '雷山小过',       number: 62, judgment: '亨，利贞。可小事，不可大事。飞鸟遗之音，不宜上，宜下，大吉。' },
  "4_8": { name: '雷地豫',         number: 16, judgment: '利建侯行师。' },
  "5_1": { name: '风天小畜',       number: 9,  judgment: '亨。密云不雨，自我西郊。' },
  "5_2": { name: '风泽中孚',       number: 61, judgment: '豚鱼吉，利涉大川，利贞。' },
  "5_3": { name: '风火家人',       number: 37, judgment: '利女贞。' },
  "5_4": { name: '风雷益',         number: 42, judgment: '利有攸往，利涉大川。' },
  "5_5": { name: '巽为风',         number: 57, judgment: '小亨，利有攸往，利见大人。' },
  "5_6": { name: '风水涣',         number: 59, judgment: '亨。王假有庙，利涉大川，利贞。' },
  "5_7": { name: '风山渐',         number: 53, judgment: '女归吉，利贞。' },
  "5_8": { name: '风地观',         number: 20, judgment: '盥而不荐，有孚颙若。' },
  "6_1": { name: '水天需',         number: 5,  judgment: '有孚，光亨，贞吉。利涉大川。' },
  "6_2": { name: '水泽节',         number: 60, judgment: '亨。苦节不可贞。' },
  "6_3": { name: '水火既济',       number: 63, judgment: '亨小，利贞。初吉终乱。' },
  "6_4": { name: '水雷屯',         number: 3,  judgment: '元亨利贞。勿用有攸往，利建侯。' },
  "6_5": { name: '水风井',         number: 48, judgment: '改邑不改井，无丧无得，往来井井。汔至，亦未繘井，羸其瓶，凶。' },
  "6_6": { name: '坎为水',         number: 29, judgment: '习坎，有孚，维心亨，行有尚。' },
  "6_7": { name: '水山蹇',         number: 39, judgment: '利西南，不利东北。利见大人，贞吉。' },
  "6_8": { name: '水地比',         number: 8,  judgment: '吉。原筮元永贞，无咎。不宁方来，后夫凶。' },
  "7_1": { name: '山天大畜',       number: 26, judgment: '利贞，不家食吉，利涉大川。' },
  "7_2": { name: '山泽损',         number: 41, judgment: '有孚，元吉，无咎，可贞，利有攸往。曷之用？二簋可用享。' },
  "7_3": { name: '山火贲',         number: 22, judgment: '亨。小利有攸往。' },
  "7_4": { name: '山雷颐',         number: 27, judgment: '贞吉。观颐，自求口实。' },
  "7_5": { name: '山风蛊',         number: 18, judgment: '元亨，利涉大川。先甲三日，后甲三日。' },
  "7_6": { name: '山水蒙',         number: 4,  judgment: '亨。匪我求童蒙，童蒙求我。初筮告，再三渎，渎则不告。利贞。' },
  "7_7": { name: '艮为山',         number: 52, judgment: '艮其背，不获其身，行其庭，不见其人，无咎。' },
  "7_8": { name: '山地剥',         number: 23, judgment: '不利有攸往。' },
  "8_1": { name: '地天泰',         number: 11, judgment: '小往大来，吉亨。' },
  "8_2": { name: '地泽临',         number: 19, judgment: '元亨利贞。至于八月有凶。' },
  "8_3": { name: '地火明夷',       number: 36, judgment: '利艰贞。' },
  "8_4": { name: '地雷复',         number: 24, judgment: '亨。出入无疾，朋来无咎。反复其道，七日来复，利有攸往。' },
  "8_5": { name: '地风升',         number: 46, judgment: '元亨，用见大人，勿恤，南征吉。' },
  "8_6": { name: '地水师',         number: 7,  judgment: '贞，丈人吉，无咎。' },
  "8_7": { name: '地山谦',         number: 15, judgment: '亨，君子有终。' },
  "8_8": { name: '坤为地',         number: 2,  judgment: '元，亨，利牝马之贞。君子有攸往，先迷后得主，利。' },
};

// ── 五行生克 ──
const ELEMENT_CYCLE = {
  generate:  { '木': '火', '火': '土', '土': '金', '金': '水', '水': '木' },
  overcome:  { '木': '土', '土': '水', '水': '火', '火': '金', '金': '木' },
};

// 八卦爻象二进制映射（bit0=初爻，阳=1）：
// 乾111=7 兑110=3 离101=5 震100=1 巽011=6 坎010=2 艮001=4 坤000=0
const NUM_TO_BIN = { 1: 7, 2: 3, 3: 5, 4: 1, 5: 6, 6: 2, 7: 4, 8: 0 };
const BIN_TO_NUM = { 7: 1, 3: 2, 5: 3, 1: 4, 6: 5, 2: 6, 4: 7, 0: 8 };

// 十二地支序数（时辰用）
const SHICHEN_NAMES = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const ANIMAL_TO_ZHI = { 鼠: 1, 牛: 2, 虎: 3, 兔: 4, 龙: 5, 蛇: 6, 马: 7, 羊: 8, 猴: 9, 鸡: 10, 狗: 11, 猪: 12 };

// ── 辅助函数 ──

function getStroke(char) {
  const hexCode = char.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0');
  const s = strokeData[hexCode];
  return s !== undefined ? s : NaN;
}

function getTrigram(num) {
  const n = ((num - 1) % 8 + 8) % 8 + 1;
  return TRIGRAMS[n];
}

function getHexagram(upperNum, lowerNum) {
  return HEXAGRAMS[`${upperNum}_${lowerNum}`] || null;
}

// 变卦：动爻翻转（bit0=初爻）
function getChangedHexagram(upperNum, lowerNum, movingLine) {
  let newUpper = upperNum;
  let newLower = lowerNum;
  const upperBinary = NUM_TO_BIN[upperNum];
  const lowerBinary = NUM_TO_BIN[lowerNum];
  if (movingLine <= 3) {
    const bitPos = movingLine - 1;
    const bit = (lowerBinary >> bitPos) & 1;
    const flipped = bit === 1 ? lowerBinary & ~(1 << bitPos) : lowerBinary | (1 << bitPos);
    newLower = BIN_TO_NUM[flipped];
  } else {
    const bitPos = movingLine - 4;
    const bit = (upperBinary >> bitPos) & 1;
    const flipped = bit === 1 ? upperBinary & ~(1 << bitPos) : upperBinary | (1 << bitPos);
    newUpper = BIN_TO_NUM[flipped];
  }
  return getHexagram(newUpper, newLower);
}

// 互卦：本卦 2-3-4 爻为下互，3-4-5 爻为上互
function getHuHexagram(upperNum, lowerNum) {
  const lowerBin = NUM_TO_BIN[lowerNum];
  const upperBin = NUM_TO_BIN[upperNum];
  const huLower = ((lowerBin >> 1) & 1) | (((lowerBin >> 2) & 1) << 1) | ((upperBin & 1) << 2);
  const huUpper = ((lowerBin >> 2) & 1) | ((upperBin & 1) << 1) | (((upperBin >> 1) & 1) << 2);
  return { upperNum: BIN_TO_NUM[huUpper], lowerNum: BIN_TO_NUM[huLower] };
}

// 当前时辰地支序数（1=子 … 12=亥）
function getShichenIndex(hour) {
  return Math.floor(((hour + 1) % 24) / 2) + 1;
}

// 卦气旺衰：按农历月判断五行旺衰
function getGuaQi(element, lunarMonth) {
  const monthWang = { 1: '木', 2: '木', 3: '土', 4: '火', 5: '火', 6: '土', 7: '金', 8: '金', 9: '土', 10: '水', 11: '水', 12: '土' };
  // 当季旺五行 → 该季衰五行（旺所克者衰）：木旺克土、火旺克金、土旺克水、金旺克木、水旺克火
  const shuaiByWang = { 木: '土', 火: '金', 土: '水', 金: '木', 水: '火' };
  const wang = monthWang[lunarMonth] || '土';
  const shuai = shuaiByWang[wang];
  const seasonNames = { 木: '春', 火: '夏', 土: '四季', 金: '秋', 水: '冬' };
  let verdict;
  if (element === wang) verdict = '旺';
  else if (element === shuai) verdict = '衰';
  else verdict = '平';
  return {
    lunar_month: lunarMonth,
    season: seasonNames[wang],
    wang_element: wang,
    body_qi: verdict,
    note: verdict === '旺' ? '体卦卦气旺盛，吉则增吉、凶可缓' :
          verdict === '衰' ? '体卦卦气衰弱，吉打折扣、凶则更凶' :
          '体卦卦气平，按体用生克断之',
  };
}

// 体用判定（含动爻者为用卦）
function getBodyUse(upperNum, lowerNum, movingLine) {
  const movingInUpper = movingLine >= 4;
  return {
    body: movingInUpper ? TRIGRAMS[lowerNum] : TRIGRAMS[upperNum],
    use:  movingInUpper ? TRIGRAMS[upperNum] : TRIGRAMS[lowerNum],
  };
}

function getBodyUseRelation(bodyElem, useElem) {
  if (bodyElem === useElem) return { relation: '比和', verdict: '大吉', description: '体用同五行，和谐一致，诸事顺遂。' };
  if (ELEMENT_CYCLE.generate[bodyElem] === useElem) return { relation: '体生用', verdict: '小凶', description: '体生用——我生者为泄气，耗损自身精力，谋事多费周折。' };
  if (ELEMENT_CYCLE.generate[useElem] === bodyElem) return { relation: '用生体', verdict: '大吉', description: '用生体——外力助我，得贵人相助，事半功倍。' };
  if (ELEMENT_CYCLE.overcome[bodyElem] === useElem) return { relation: '体克用', verdict: '中吉', description: '体克用——我能掌控局面，事可成，但需努力、见效较慢。' };
  if (ELEMENT_CYCLE.overcome[useElem] === bodyElem) return { relation: '用克体', verdict: '凶', description: '用克体——外力克制于我，所谋难成，宜守不宜攻。' };
  return { relation: '未知', verdict: '平', description: '' };
}

// ── 起卦核心 ──

// 一字占
function divinateOneChar(char, shichenIndex) {
  const total = getStroke(char);
  if (isNaN(total)) return { error: `无法获取"${char}"的笔画数，请换一个字，或省略字参数改用时辰占。` };
  if (total <= 1) return { error: `"${char}"仅${total}画，独体单画字不宜一字占（原书：不可起卦），请省略字参数改用时辰占。` };

  const hexCode = char.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0');
  const struct = charStructure[hexCode];
  let upperNum, lowerNum, splitMethod, front, back, movingLine;

  if (struct) {
    // 方式A：结构拆解（左右/上下/包围）
    front = strokeData[struct.c1_hex] || 0;
    back  = Math.max(strokeData[struct.c2_hex] || 0, 1);
    upperNum = ((front - 1) % 8) + 1;
    lowerNum = ((back  - 1) % 8) + 1;
    movingLine = ((total - 1) % 6) + 1;
    const typeNames = { LR: '左右部件', TB: '上下部件', SW: '包围部件' };
    splitMethod = typeNames[struct.type] || '汉字结构拆解';
  } else if (strokeDirection[hexCode]) {
    // 方式C：笔画方向分阴阳（传统测字技法）
    const d = strokeDirection[hexCode];
    front = d.yang;
    back  = d.yin;
    upperNum = front === 0 ? 8 : ((front - 1) % 8) + 1; // 0画边取坤8（余0作8）
    lowerNum = back === 0 ? 8 : ((back  - 1) % 8) + 1;
    movingLine = ((total - 1) % 6) + 1;
    splitMethod = `笔画方向分阴阳（阳${front}画 阴${back}画）`;
  } else {
    // 方式B'：笔画平分 + 时辰加数（天轻清地重浊；加数法打破必比和）
    front = Math.max(Math.floor(total / 2), 1);       // 上卦取少（天轻清）
    back  = Math.max(Math.ceil(total / 2), 1) + shichenIndex; // 下卦取多 + 时辰数
    upperNum = ((front - 1) % 8) + 1;
    lowerNum = ((back  - 1) % 8) + 1;
    movingLine = ((total + shichenIndex - 1) % 6) + 1;
    splitMethod = `笔画平分（上${front}画 下${total - front}画）+ 时辰数${shichenIndex}（${SHICHEN_NAMES[shichenIndex - 1]}时）`;
  }

  return { total, upperNum, lowerNum, movingLine, splitMethod, front, back };
}

// 多字占
function divinateMultiChars(chars) {
  const n = chars.length;
  if (n === 2) {
    // 二字占：前字笔画为上卦，后字笔画为下卦
    const s1 = getStroke(chars[0]);
    const s2 = getStroke(chars[1]);
    if (isNaN(s1) || isNaN(s2)) return { error: '二字中有的字无法获取笔画数，请换字。' };
    return {
      upperNum: ((s1 - 1) % 8) + 1,
      lowerNum: ((s2 - 1) % 8) + 1,
      movingLine: (((s1 + s2) - 1) % 6) + 1,
      splitMethod: `二字占（前字${s1}画为上卦，后字${s2}画为下卦）`,
      total: s1 + s2,
    };
  }
  // 三字以上：字数起卦，停匀平分、不匀上少下多（天轻清地重浊）
  const up = Math.floor(n / 2);
  const down = Math.ceil(n / 2);
  return {
    upperNum: ((up - 1) % 8) + 1,
    lowerNum: ((down - 1) % 8) + 1,
    movingLine: ((n - 1) % 6) + 1,
    splitMethod: `${n}字占（按字数：上卦${up}字 下卦${down}字）`,
    total: n,
  };
}

// 时辰占（年月日时起卦）
function divinateByTime(now) {
  const lunar = solar.solar2lunar(now.getFullYear(), now.getMonth() + 1, now.getDate());
  const yearZhi = ANIMAL_TO_ZHI[lunar.animal] || 7;
  const month = lunar.lMonth;
  const day = lunar.lDay;
  const shichenIndex = getShichenIndex(now.getHours());
  const upSum = yearZhi + month + day;
  const downSum = upSum + shichenIndex;
  return {
    upperNum: ((upSum - 1) % 8) + 1,
    lowerNum: ((downSum - 1) % 8) + 1,
    movingLine: ((downSum - 1) % 6) + 1,
    splitMethod: `年月日时起卦（年支${SHICHEN_NAMES[yearZhi - 1]}${yearZhi} + 月${month} + 日${day} 为上卦；加时支${SHICHEN_NAMES[shichenIndex - 1]}${shichenIndex} 为下卦）`,
    lunarInfo: {
      year: lunar.lYear,
      month: lunar.lMonth,
      day: lunar.lDay,
      isLeap: lunar.isLeap,
      animal: lunar.animal,
      monthCn: lunar.monthCn,
      dayCn: lunar.dayCn,
    },
    shichen: SHICHEN_NAMES[shichenIndex - 1],
    total: downSum,
  };
}

// ── 数字占（报数起卦，数字个数不定，以空格分隔）──
// n=1：上卦=数1，下卦=数1+时辰，动爻=数1+时辰
// n=2：上卦=数1，下卦=数2，动爻=数1+数2+时辰
// n≥3：前一半个数之和为上卦，后一半之和为下卦（不匀上少下多），动爻=总和+时辰
function divinateByNumbers(nums, shichenIndex) {
  const mod8 = (x) => ((x - 1) % 8 + 8) % 8 + 1;
  const mod6 = (x) => ((x - 1) % 6 + 6) % 6 + 1;
  const n = nums.length;
  const sum = nums.reduce((a, b) => a + b, 0);
  let upperNum, lowerNum, movingLine, splitMethod;
  if (n === 1) {
    upperNum = mod8(nums[0]);
    lowerNum = mod8(nums[0] + shichenIndex);
    movingLine = mod6(nums[0] + shichenIndex);
    splitMethod = `一数占（${nums[0]} 为上卦；加时辰数${shichenIndex}（${SHICHEN_NAMES[shichenIndex - 1]}时）为下卦）`;
  } else if (n === 2) {
    upperNum = mod8(nums[0]);
    lowerNum = mod8(nums[1]);
    movingLine = mod6(sum + shichenIndex);
    splitMethod = `二数占（${nums[0]} 为上卦，${nums[1]} 为下卦）`;
  } else {
    const up = Math.floor(n / 2);
    const upSum = nums.slice(0, up).reduce((a, b) => a + b, 0);
    const downSum = nums.slice(up).reduce((a, b) => a + b, 0);
    upperNum = mod8(upSum);
    lowerNum = mod8(downSum);
    movingLine = mod6(sum + shichenIndex);
    splitMethod = `${n}数占（前${up}个数之和${upSum}为上卦，后${n - up}个数之和${downSum}为下卦）`;
  }
  return { upperNum, lowerNum, movingLine, splitMethod, total: sum, nums };
}

// ── 物象占（观物取象：主物象为上卦，方位/次物象为下卦）──
// 上/下卦可传：八卦名（乾兑离震巽坎艮坤）｜方位（东南西北/东南/东北/西南/西北）｜先天数 1-8
const TRIGRAM_NAME_TO_NUM = { 乾: 1, 兑: 2, 离: 3, 震: 4, 巽: 5, 坎: 6, 艮: 7, 坤: 8 };
const DIRECTION_TO_TRIGRAM = { 东: 4, 南: 3, 西: 2, 北: 6, 东南: 5, 东北: 7, 西南: 8, 西北: 1 };

function resolveTrigram(ref) {
  if (typeof ref === 'number') return ((ref - 1) % 8 + 8) % 8 + 1;
  const s = String(ref).trim();
  if (/^\d+$/.test(s)) return ((parseInt(s, 10) - 1) % 8 + 8) % 8 + 1;
  if (TRIGRAM_NAME_TO_NUM[s]) return TRIGRAM_NAME_TO_NUM[s];
  if (DIRECTION_TO_TRIGRAM[s]) return DIRECTION_TO_TRIGRAM[s];
  return null;
}

function divinateByObject(upperRef, lowerRef, shichenIndex, movingLine) {
  const upperNum = resolveTrigram(upperRef);
  const lowerNum = resolveTrigram(lowerRef);
  if (!upperNum || !lowerNum) {
    return { error: `无法识别物象卦/方位：「${upperRef}」「${lowerRef}」。请用八卦名（乾兑离震巽坎艮坤）、方位（东南西北/东南/东北/西南/西北）或先天数 1-8。` };
  }
  if (movingLine === undefined || movingLine === null || isNaN(movingLine)) {
    movingLine = ((upperNum + lowerNum + shichenIndex - 1) % 6) + 1;
  } else {
    movingLine = ((movingLine - 1) % 6 + 6) % 6 + 1;
  }
  const lowerDesc = DIRECTION_TO_TRIGRAM[String(lowerRef).trim()]
    ? `方位${lowerRef}（${TRIGRAMS[lowerNum].name}）`
    : `${lowerRef}（${TRIGRAMS[lowerNum].name}）`;
  return {
    upperNum,
    lowerNum,
    movingLine,
    splitMethod: `物象占（${upperRef}→${TRIGRAMS[upperNum].name}为上卦，${lowerDesc}为下卦；动爻=(上${upperNum}+下${lowerNum}+时辰${shichenIndex})余6）`,
    total: upperNum + lowerNum,
  };
}

// ── 组装结果 ──
function buildResult(calc, topic, methodName) {
  const { upperNum, lowerNum, movingLine, splitMethod } = calc;
  const upperTri = TRIGRAMS[upperNum];
  const lowerTri = TRIGRAMS[lowerNum];
  const original = getHexagram(upperNum, lowerNum);
  const changed = getChangedHexagram(upperNum, lowerNum, movingLine);
  const hu = getHuHexagram(upperNum, lowerNum);
  const huHex = getHexagram(hu.upperNum, hu.lowerNum);
  const { body, use } = getBodyUse(upperNum, lowerNum, movingLine);
  const buRel = getBodyUseRelation(body.element, use.element);
  const lineNames = ['初爻', '二爻', '三爻', '四爻', '五爻', '上爻'];

  // 卦气旺衰：体卦五行 vs 当前农历月（时辰占/多字占无农历月时用公历月近似）
  const now = new Date();
  const lunar = solar.solar2lunar(now.getFullYear(), now.getMonth() + 1, now.getDate());
  const guaQi = getGuaQi(body.element, lunar.lMonth);

  const result = {
    method: methodName,
    topic: topic || '',
    input: calc.input || null,
    split: { method: splitMethod, detail: calc },
    time: {
      solar: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`,
      lunar: `${lunar.gzYear || ''}年${lunar.monthCn || lunar.lMonth + '月'}${lunar.dayCn || lunar.lDay + '日'}`,
      shichen: SHICHEN_NAMES[getShichenIndex(now.getHours()) - 1] + '时',
    },
    upper_trigram: upperTri,
    lower_trigram: lowerTri,
    moving_line: { number: movingLine, name: lineNames[movingLine - 1] },
    original_hexagram: { ...original, upper: upperTri.name + upperTri.symbol, lower: lowerTri.name + lowerTri.symbol },
    hu_hexagram: huHex ? { ...huHex, upper: TRIGRAMS[hu.upperNum].name + TRIGRAMS[hu.upperNum].symbol, lower: TRIGRAMS[hu.lowerNum].name + TRIGRAMS[hu.lowerNum].symbol } : null,
    changed_hexagram: changed ? { ...changed } : null,
    body_use: { body, use, ...buRel },
    gua_qi: guaQi,
  };
  return result;
}

// ── CLI ──
const args = process.argv.slice(2);
const topic = args[0] || '';
const rest = args.slice(1);
const shichenIndex = getShichenIndex(new Date().getHours());

function fail(err) {
  console.log(JSON.stringify({ error: err }, null, 2));
  process.exit(1);
}

let result;
if (rest[0] === '--object') {
  // 物象占：--object <上卦名|数> <下卦名|数|方位> [动爻]
  const upperRef = rest[1];
  const lowerRef = rest[2];
  const movingLineArg = rest[3] !== undefined ? parseInt(rest[3], 10) : undefined;
  if (!upperRef || !lowerRef) fail('物象占需提供上卦与下卦：--object <上卦> <下卦> [动爻]');
  const calc = divinateByObject(upperRef, lowerRef, shichenIndex, movingLineArg);
  if (calc.error) fail(calc.error);
  result = buildResult({ ...calc, input: { upper: upperRef, lower: lowerRef, moving_line: calc.movingLine } }, topic, '物象占');
} else if (rest.length > 0 && rest.every((a) => /^\d+$/.test(a))) {
  // 数字占（数字个数不定，空格分隔）
  const nums = rest.map((a) => parseInt(a, 10));
  const calc = divinateByNumbers(nums, shichenIndex);
  if (calc.error) fail(calc.error);
  result = buildResult({ ...calc, input: { numbers: nums, count: nums.length } }, topic, '数字占');
} else if (rest.length === 0) {
  // 时辰占
  result = buildResult(divinateByTime(new Date()), topic, '时辰占（年月日时起卦）');
} else {
  // 字占（多个参数直接拼接，不加分隔符）
  const charArg = rest.join('');
  if ([...charArg].length === 1) {
    const calc = divinateOneChar(charArg, shichenIndex);
    if (calc.error) fail(calc.error);
    result = buildResult({ ...calc, input: { character: charArg, total_strokes: calc.total } }, topic, '一字占');
  } else {
    const chars = [...charArg];
    const calc = divinateMultiChars(chars);
    if (calc.error) fail(calc.error);
    result = buildResult({ ...calc, input: { chars: charArg, count: chars.length } }, topic, chars.length === 2 ? '二字占' : '多字占');
  }
}

console.log(JSON.stringify(result, null, 2));
