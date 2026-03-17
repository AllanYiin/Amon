# SVG 投影片製作規範（製作階段參考）

本文件在你要用 SVG 產出投影片時使用。

## 核心禁令

- UNDER NO CIRCUMSTANCES SHALL LINE SIMPLIFICATION BE PERFORMED ON SVG MARKUP.
- 禁止 SVG 節略/簡化原始碼（包含「示意」省略大量 path/attrs）。

## 交付與預覽規則

- 必須「可線上預覽」：用三個反引號包住，語言標示必須是 `svg`。
- 禁止把 SVG 包在 HTML 或其他標記中。
- 同時存檔：
  - `/mnt/data/{檔名}.svg`
  - 並輸出對應 png 預覽 `/mnt/data/{檔名}.png`

## 檢查流程（建議）

1) SVG 設計完成後先存檔到 /mnt/data
2) 轉換成 PNG（僅用於視覺檢查，不是拿 PNG 貼回投影片）
3) 使用視覺能力讀取 PNG，自行檢查：
   - 是否超出畫布
   - 是否文字過小/模糊（尤其避免 stroke）
   - 是否元素重疊、對齊不齊
   - 視覺層次是否足夠（避免只有文字）
4) 若 PNG 預覽失敗或畫面異常：參照內部文件《svg無法正確預覽原因.pdf》逐項排查

## 圖示與意象（上網挑選）

- 每個簡報主題至少延伸 3 種以上視覺意象
- 主動上網搜尋適用的 SVG icon（不得簡化原始碼）
- 每個 SVG icon 使用前確認：
  - bbox 邊界無遮擋
  - 可搭配背景色或透明層混合使用

## 圖片 placeholder

若需要插入截圖或特別圖片：
- 在畫面中保留空間
- 以 Placeholder 命名（清楚標示圖的用途/來源/尺寸）
