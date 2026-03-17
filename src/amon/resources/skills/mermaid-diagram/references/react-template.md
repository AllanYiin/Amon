# React Artifact 模板（Mermaid）

當使用者需要互動式圖表（如可切換主題、動態更新資料）時，使用 React artifact。

## 基本 React 模板

```jsx
import { useState, useEffect, useRef } from "react";

export default function MermaidDiagram() {
  const containerRef = useRef(null);
  const [error, setError] = useState(null);

  const diagramCode = `
flowchart TD
    A([開始]) --> B{使用者已登入?}
    B -- 是 --> C[顯示首頁]
    B -- 否 --> D[跳轉登入頁]
  `;

  useEffect(() => {
    const loadMermaid = async () => {
      try {
        const { default: mermaid } = await import(
          "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
        );
        mermaid.initialize({
          startOnLoad: false,
          theme: "default",
          themeVariables: {
            fontFamily: '"Noto Sans TC", "Microsoft JhengHei", sans-serif',
          },
        });

        if (containerRef.current) {
          containerRef.current.innerHTML = "";
          const id = "mermaid-" + Date.now();
          const { svg } = await mermaid.render(id, diagramCode.trim());
          containerRef.current.innerHTML = svg;
        }
      } catch (err) {
        setError(err.message);
      }
    };
    loadMermaid();
  }, []);

  return (
    <div className="p-4 bg-white rounded-lg shadow">
      {error ? (
        <div className="text-red-500">
          <p>渲染錯誤：</p>
          <pre className="text-sm bg-red-50 p-2 rounded">{error}</pre>
        </div>
      ) : (
        <div ref={containerRef} className="flex justify-center" />
      )}
    </div>
  );
}
```

## 多圖切換模板

```jsx
import { useState, useEffect, useRef } from "react";

const diagrams = {
  流程圖: `flowchart TD
    A[開始] --> B{判斷}
    B -- 是 --> C[動作A]
    B -- 否 --> D[動作B]`,
  序列圖: `sequenceDiagram
    participant 前端
    participant 後端
    前端->>後端: 請求資料
    後端-->>前端: 回傳結果`,
  狀態圖: `stateDiagram-v2
    [*] --> 待處理
    待處理 --> 處理中 : 開始
    處理中 --> 完成 : 成功
    完成 --> [*]`,
};

export default function MultiDiagram() {
  const [selected, setSelected] = useState("流程圖");
  const containerRef = useRef(null);

  useEffect(() => {
    const render = async () => {
      const { default: mermaid } = await import(
        "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
      );
      mermaid.initialize({ startOnLoad: false, theme: "default" });
      if (containerRef.current) {
        containerRef.current.innerHTML = "";
        const id = "m-" + Date.now();
        const { svg } = await mermaid.render(id, diagrams[selected]);
        containerRef.current.innerHTML = svg;
      }
    };
    render();
  }, [selected]);

  return (
    <div className="p-4">
      <div className="flex gap-2 mb-4">
        {Object.keys(diagrams).map((name) => (
          <button
            key={name}
            onClick={() => setSelected(name)}
            className={`px-3 py-1 rounded ${
              selected === name
                ? "bg-blue-500 text-white"
                : "bg-gray-200 text-gray-700"
            }`}
          >
            {name}
          </button>
        ))}
      </div>
      <div ref={containerRef} className="bg-white p-4 rounded border" />
    </div>
  );
}
```

## 主題切換模板

```jsx
const themes = ["default", "dark", "forest", "neutral", "base"];
// 在 mermaid.initialize 中動態傳入 theme
```
