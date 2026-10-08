# 数据来源与许可

## 牌义文本

- **关键词层**：A. E. Waite《The Pictorial Key to the Tarot》（1911，**公有领域**）的牌义关键词。原文取自已公开的 JSON 转录：[ekelen/tarot-api](https://github.com/ekelen/tarot-api)（`scraper/maj_text.json`、`scraper/min_text.json`，MIT）。
- **中文释义**：在上述关键词基础上译写并补足现代心理塔罗视角（画面意象、恋爱、事业、建议），由本机 DSH 会话生成，未逐字复制任何受版权保护的现代牌义书。
- **画面意象**：依据 Rider-Waite-Smith（1909，公有领域）牌面本身描述。

## 方法与结构

- 牌阵定义、牌间关系体系（愚人之旅 / 数字旅程 / 牌性 / 对位牌 / 宫廷牌）、透镜模型、反巴纳姆与安全边界：参照 [daman-ovo-0404/tarot-skill](https://github.com/daman-ovo-0404/tarot-skill)（MIT）与 [ClawHub eamanc-lab/tarot-reading v1.2.0](https://docs.clawhub.ai/eamanc-lab/skills/tarot-reading)（MIT-0）的思路重写，正文为本机自写，非原文搬运。
- 与原作的关键差别：**抽牌权归用户**（本 skill 不随机抽牌，只有用户明确要求时才用 `deal.py --auto`），因此不沿用原作的随机抽牌脚本。

## 许可

本 skill 目录内容按 MIT 使用；再分发时保留上面的来源链接与 Waite 1911 公有领域出处。
