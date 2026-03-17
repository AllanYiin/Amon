# Source notes

這份筆記把新增附件與外部文章轉成 `humanize-text` 可直接採用的規則，避免只停在觀念摘要。

## Local PDF

- 檔案：`C:/Users/allan/Downloads/語言模型書寫風格分析.pdf`
- 可直接吸收的結論：
  - 「不像人」常不是單一語病，而是多個訊號疊加，例如過度平滑、安全、模板化、句長過度均勻、標點節奏過度規整、在地語感不對。
  - 推論期最可落地的做法不是亂加錯字，而是 `style spec + few-shot + negative constraints + rewriting/postprocess`。
  - 去模板、去重複、調整句長與標點節奏、做地區化，是比「刻意裝不完美」更穩的做法。
  - 對繁中尤其要處理台灣語境、過度正式、列表感與轉折詞濫用。

## Web notes

### LINE 文章

來源：[line.newspaper.tw/2026/03/imitate.html](https://line.newspaper.tw/2026/03/imitate.html)

- 可直接吸收的結論：
  - 人類文章常有不平均的重點分配，不會每段都像模板一樣平均。
  - 太工整、太完整、太像「把該講的都講完」反而容易露出機器感。
  - 更自然的寫法通常會保留取景角度、情緒焦點與選擇性細節，而不是平均鋪陳。

### BruceWind 文章

來源：[iambrucewind.com/20251116-brucewind-aiwriting](https://iambrucewind.com/20251116-brucewind-aiwriting/)

- 可直接吸收的結論：
  - AI 常以定義、摘要、教學式鋪陳起手，轉折詞過多，整篇太像講義。
  - 要減少「AI 味」，應刪掉不必要的解說骨架，不要讓第一段總在下定義，最後一段總在總結。
  - 更像人的改寫不是把文章弄亂，而是讓段落有輕重、語氣有立場、細節有取捨。

## Rules promoted to the skill

1. 預設掃描並移除教學模板句。
2. 若段落長度與句法過於平均，主動打散節奏。
3. 若使用者提供風格樣本，學節奏、距離感與觀點密度，不抄句子。
4. 優先把內容改得「像作者有取捨」，而不是「像系統把所有點列完」。
5. 在繁中情境下，先修語感與在地性，再談華麗修辭。
