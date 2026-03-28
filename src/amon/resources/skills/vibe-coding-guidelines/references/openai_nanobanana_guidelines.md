\# AI 功能開發通用準則



（OpenAI Responses + Nano Banana 2 / Gemini，適用 Chat / STT / T2I / I2I）



---



\## 1. 這份文件到底在幹嘛



目標很單純：



> 未來任何人在專案裡要「加 AI 功能」時，可以打開這份文件，就知道

> \*\*Chat 用什麼 API？怎麼 streaming？哪個 model？STT 怎麼選？生圖用誰？\*\*



根據你的要求，這份準則預設：



\* \*\*金鑰一律放環境變數\*\*

\* \*\*對話一律用 Streaming\*\*

\* \*\*對話一律走 OpenAI Responses API（不要再開新的 chat/completions 宗派）\*\*

\* \*\*生圖預設用 Nano Banana 2（實作上是包 Google Gemini 3.1 Flash Image API）\*\*



程式語言示範用 Python，但設計思路是語言無關的。



---



\## 2. 全域設計原則



\### 2.1 能力分層，而不是廠商分層



先想清楚你需要的「能力」，再決定用哪一家：



\* `ChatClient`：對話 / 多輪 / 視覺理解

\* `STTClient`：語音轉文字

\* `ImageClient`：T2I / I2I 圖像生成



\*\*上層業務只碰這三種介面\*\*，不知道底下是 OpenAI / NanoBanana / 其它廠商。



你現在在 `llm.py` 裡已經有類似「以能力為中心 + streaming 封裝」的寫法，可以直接當這份設計的原型。



---



\### 2.2 金鑰 / Model / 版本管理



通用原則：



\* OpenAI：



&nbsp; \* `OPENAI\_API\_KEY`

&nbsp; \* `OPENAI\_RESPONSES\_MODEL`（建議用 env 控制，預設可用 `gpt-5-mini`；\*\*不要把 mini/nano 視為禁用\*\*，而是依成本/延遲/品質做取捨）(\[OpenAI Platform]\[1])

\* Nano Banana 2 / Gemini：



&nbsp; \* `GEMINI\_API\_KEY`

&nbsp; \* `NB\_IMAGE\_MODEL`（預設 `gemini-3.1-flash-image-preview` 類型）



程式裡 \*\*不要硬寫 model 名稱\*\*，全部從 env 讀：



```python

import os



OPENAI\_MODEL = os.getenv("OPENAI\_RESPONSES\_MODEL", "gpt-5-mini")

NB\_IMAGE\_MODEL = os.getenv("NB\_IMAGE\_MODEL", "gemini-3.1-flash-image-preview")

```



版本錯用最常見的兩種：



1\. 拿純文字 model 去做 STT / Vision / T2I

2\. 拿舊 endpoint（例如 chat.completions）去叫新 model



預防方式就是：

\*\*「能力 → endpoint → model」對應關係寫在註解 \& config 裡\*\*，而不是藏在腦子裡。



---



\### 2.3 Streaming 是預設，而不是加分題



對話一律 streaming，有幾個好處：



\* UX：使用者可以看到逐字冒出來的回答

\* Dev：錯誤通常會提早暴露（而不是 60 秒後才丟 Exception）

\* 架構：跟將來接 Realtime API 一致思路(\[OpenAI Platform]\[2])



建議 pattern：



\* \*\*最底層\*\*：對接 OpenAI Responses streaming（同步 iterator）

\* \*\*中間層\*\*：用 background thread + `asyncio.Queue` 把它變成 async generator

&nbsp; 這個 pattern 你在 `llm.py` 已經實作過，可以重用。

\* \*\*最上層\*\*：業務邏輯只看到 `async for token in chat.stream(...): ...`



---



\## 3. Chat（含多輪對話與視覺）：OpenAI Responses + Streaming



這一段是這份文件的核心。



\### 3.1 通用資料結構：對話 + 視覺



用 Responses API 的推薦寫法：



\* `input` 是 list，每個元素是一個 message：

&nbsp; `{"role": "user" | "assistant" | "system", "content": ...}`(\[OpenAI Platform]\[3])

\* `content` 可以是：



&nbsp; \* 純文字：`"hello world"`

&nbsp; \* 或 parts list：`\[{"type": "input\_text", "text": ...}, {"type": "input\_image", ...}]`(\[OpenAI Platform]\[4])



通用型別（簡化）：



```python

from typing import Literal, TypedDict, List, Union, Dict, Any



class TextPart(TypedDict):

&nbsp;   type: Literal\["input\_text"]

&nbsp;   text: str



class ImagePart(TypedDict):

&nbsp;   type: Literal\["input\_image"]

&nbsp;   image: Dict\[str, Any]  # e.g. {"url": "..."} 或 {"data": "...", "format": "png"}



ContentPart = Union\[TextPart, ImagePart]



class ChatMessage(TypedDict, total=False):

&nbsp;   role: Literal\["system", "user", "assistant"]

&nbsp;   content: Union\[str, List\[ContentPart]]

```



多輪 + 視覺的 history 就是一個 `List\[ChatMessage]`。



---



\### 3.2 ChatClient 介面（只專注在 streaming）



```python

\# chat\_client.py

from dataclasses import dataclass

from typing import List, AsyncGenerator, Optional

import os



@dataclass

class ChatConfig:

&nbsp;   model: str = os.getenv("OPENAI\_RESPONSES\_MODEL", "gpt-4.1-mini")

&nbsp;   temperature: float = 0.6

&nbsp;   max\_output\_tokens: int = 2048

&nbsp;   timeout: float = float(os.getenv("OPENAI\_TIMEOUT", "60"))



class ChatClient:

&nbsp;   """抽象介面：任何廠商的 chat adapter 都要實作這兩個方法。"""



&nbsp;   async def stream(

&nbsp;       self,

&nbsp;       messages: List\[dict],

&nbsp;       config: Optional\[ChatConfig] = None,

&nbsp;   ) -> AsyncGenerator\[str, None]:

&nbsp;       raise NotImplementedError



&nbsp;   async def stream\_to\_text(

&nbsp;       self,

&nbsp;       messages: List\[dict],

&nbsp;       config: Optional\[ChatConfig] = None,

&nbsp;   ) -> str:

&nbsp;       """糖衣：內部仍用 streaming，只是幫你把 token 拼回一個字串。"""

&nbsp;       chunks = \[]

&nbsp;       async for token in self.stream(messages, config=config):

&nbsp;           chunks.append(token)

&nbsp;       return "".join(chunks).strip()

```



---



\### 3.3 OpenAI Responses 的 Streaming 實作（含多輪 + 視覺）



這裡重點是：



\* 使用 `client.responses.create(..., stream=True, input=messages)` 作為底層 stream(\[OpenAI Platform]\[2])

\* 用 background thread + `asyncio.Queue` 把它變成 async generator（pattern 取自你現在的 `llm.py`）。



```python

\# openai\_chat\_client.py

from typing import List, AsyncGenerator, Optional, Any, Dict

from dataclasses import dataclass

import asyncio

import threading

import os



from openai import OpenAI

from .chat\_client import ChatClient, ChatConfig



@dataclass

class \_StreamEvent:

&nbsp;   type: str

&nbsp;   delta: str





class OpenAIResponsesChatClient(ChatClient):

&nbsp;   def \_\_init\_\_(self):

&nbsp;       api\_key = os.getenv("OPENAI\_API\_KEY")

&nbsp;       if not api\_key:

&nbsp;           raise RuntimeError("OPENAI\_API\_KEY 未設定")

&nbsp;       self.\_client = OpenAI(api\_key=api\_key)



&nbsp;   async def stream(

&nbsp;       self,

&nbsp;       messages: List\[Dict\[str, Any]],

&nbsp;       config: Optional\[ChatConfig] = None,

&nbsp;   ) -> AsyncGenerator\[str, None]:

&nbsp;       cfg = config or ChatConfig()

&nbsp;       loop = asyncio.get\_running\_loop()

&nbsp;       q: asyncio.Queue\[Optional\[\_StreamEvent]] = asyncio.Queue()

&nbsp;       STOP = None  # sentinel



&nbsp;       def worker():

&nbsp;           try:

&nbsp;               # 這裡只示範最常見的 text streaming。

&nbsp;               # 事件型別與欄位名稱請以官方文件為準。

&nbsp;               stream = self.\_client.responses.create(

&nbsp;                   model=cfg.model,

&nbsp;                   input=messages,

&nbsp;                   temperature=cfg.temperature,

&nbsp;                   max\_output\_tokens=cfg.max\_output\_tokens,

&nbsp;                   stream=True,

&nbsp;                   timeout=cfg.timeout,

&nbsp;               )

&nbsp;               for event in stream:

&nbsp;                   # 典型寫法：過濾出 text delta 事件

&nbsp;                   # （官方文件中常見 type 類似 "response.output\_text.delta" 等）:contentReference\[oaicite:9]{index=9}

&nbsp;                   etype = getattr(event, "type", "") or ""

&nbsp;                   if "output\_text" in etype and "delta" in etype:

&nbsp;                       delta = getattr(event, "delta", "") or ""

&nbsp;                       if delta:

&nbsp;                           loop.call\_soon\_threadsafe(

&nbsp;                               q.put\_nowait,

&nbsp;                               \_StreamEvent(type=etype, delta=delta),

&nbsp;                           )

&nbsp;           except Exception as e:

&nbsp;               # 實務上用 logger

&nbsp;               loop.call\_soon\_threadsafe(

&nbsp;                   q.put\_nowait,

&nbsp;                   \_StreamEvent(type="error", delta=f"\[stream\_error] {e}"),

&nbsp;               )

&nbsp;           finally:

&nbsp;               loop.call\_soon\_threadsafe(q.put\_nowait, STOP)



&nbsp;       threading.Thread(target=worker, daemon=True).start()



&nbsp;       while True:

&nbsp;           item = await q.get()

&nbsp;           if item is STOP:

&nbsp;               break

&nbsp;           if item.type == "error":

&nbsp;               # 視情況要不要直接 raise

&nbsp;               print(item.delta)

&nbsp;               continue

&nbsp;           yield item.delta

```



> 註：上面對 `event.type` / `event.delta` 的使用，是依照官方「Responses Streaming」文件裡示範的 event 型別概念整理的簡化版，實際欄位請以最新文件為準。(\[OpenAI Platform]\[2])



---



\### 3.4 純文字多輪對話使用範例



```python

\# example\_chat\_text.py

import asyncio

from app.services.openai\_chat\_client import OpenAIResponsesChatClient, ChatConfig



async def main():

&nbsp;   chat = OpenAIResponsesChatClient()



&nbsp;   history = \[

&nbsp;       {

&nbsp;           "role": "system",

&nbsp;           "content": "你是一位樂於解釋技術概念的 AI 助理，永遠使用繁體中文回答。",

&nbsp;       },

&nbsp;       {

&nbsp;           "role": "user",

&nbsp;           "content": "可以簡單說明一下什麼是向量資料庫嗎？",

&nbsp;       },

&nbsp;   ]



&nbsp;   print("=== Streaming 回應 ===")

&nbsp;   async for token in chat.stream(history, ChatConfig(temperature=0.4)):

&nbsp;       print(token, end="", flush=True)



&nbsp;   # 下一輪：把模型回覆 append 進 history，然後再加一個新問題即可。

&nbsp;   # （實務上你會把上一輪回答內容收集起來，存進 DB 或 session。）



if \_\_name\_\_ == "\_\_main\_\_":

&nbsp;   asyncio.run(main())

```



---



\### 3.5 視覺對話（帶圖片）範例



這裡示範「使用者上傳一張圖片 + 文字提問」，

重點在 `content` 是一個 parts list：



```python

\# example\_chat\_vision.py

import asyncio

import base64

from pathlib import Path

from typing import List, Dict, Any



from app.services.openai\_chat\_client import OpenAIResponsesChatClient



def load\_image\_part(path: str) -> Dict\[str, Any]:

&nbsp;   buf = Path(path).read\_bytes()

&nbsp;   b64 = base64.b64encode(buf).decode("ascii")

&nbsp;   return {

&nbsp;       "type": "input\_image",

&nbsp;       "image": {

&nbsp;           # 這裡以 inline base64 為例；你也可以用 image\_url。:contentReference\[oaicite:11]{index=11}

&nbsp;           "data": b64,

&nbsp;           "format": "png",

&nbsp;       },

&nbsp;   }



async def main():

&nbsp;   chat = OpenAIResponsesChatClient()



&nbsp;   img\_part = load\_image\_part("assets/cat.png")



&nbsp;   messages: List\[Dict\[str, Any]] = \[

&nbsp;       {

&nbsp;           "role": "system",

&nbsp;           "content": "你是一位圖像說明助手，永遠使用繁體中文。",

&nbsp;       },

&nbsp;       {

&nbsp;           "role": "user",

&nbsp;           "content": \[

&nbsp;               {

&nbsp;                   "type": "input\_text",

&nbsp;                   "text": "請描述這張圖片，並順便幫這隻貓取一個台味一點的暱稱。",

&nbsp;               },

&nbsp;               img\_part,

&nbsp;           ],

&nbsp;       },

&nbsp;   ]



&nbsp;   async for token in chat.stream(messages):

&nbsp;       print(token, end="", flush=True)



if \_\_name\_\_ == "\_\_main\_\_":

&nbsp;   asyncio.run(main())

```



這個 pattern 之後可以重複用在：



\* 上傳合約 PDF + 問條款（用 file / vision）

\* 上傳 UI screenshot + 問 UX 問題

\* 上傳報表截圖 + 請模型解釋趨勢



---



\## 4. Speech-to-Text（STT）：Whisper + Responses 後備



STT 的通用策略：



1\. 優先使用 \*\*專用 STT 模型\*\*（如 `whisper-1`）做轉錄

2\. 若失敗，再用 Responses + `input\_audio` 模式請 LLM 幫忙轉錄（或做更高階理解）



你的 `openai\_service.py` 本來就這樣做，這是一個好 pattern。



\### 4.1 STT 介面



```python

\# stt\_client.py

from dataclasses import dataclass

from typing import Optional



@dataclass

class STTConfig:

&nbsp;   target\_lang: str = "zh-TW"

&nbsp;   prompt: Optional\[str] = None  # 語境提示，例如「會議記錄」「客服通話」

&nbsp;   timeout: float = float(os.getenv("OPENAI\_TIMEOUT", "60"))



class STTClient:

&nbsp;   def transcribe(

&nbsp;       self,

&nbsp;       audio\_bytes: bytes,

&nbsp;       mime\_type: str,

&nbsp;       config: Optional\[STTConfig] = None,

&nbsp;   ) -> str:

&nbsp;       raise NotImplementedError

```



\### 4.2 OpenAI STT 實作：Whisper → Responses Fallback



```python

\# openai\_stt\_client.py

import base64

import os

from typing import Optional

from openai import OpenAI



from .stt\_client import STTClient, STTConfig



class OpenAIWhisperSTTClient(STTClient):

&nbsp;   def \_\_init\_\_(self):

&nbsp;       api\_key = os.getenv("OPENAI\_API\_KEY")

&nbsp;       if not api\_key:

&nbsp;           raise RuntimeError("OPENAI\_API\_KEY 未設定，STT 無法啟用")

&nbsp;       self.\_client = OpenAI(api\_key=api\_key)



&nbsp;   def \_whisper(

&nbsp;       self,

&nbsp;       audio\_bytes: bytes,

&nbsp;       mime\_type: str,

&nbsp;       cfg: STTConfig,

&nbsp;   ) -> str:

&nbsp;       tr = self.\_client.audio.transcriptions.create(

&nbsp;           model=os.getenv("OPENAI\_STT\_MODEL", "whisper-1"),

&nbsp;           file=("audio", audio\_bytes, mime\_type),

&nbsp;           timeout=cfg.timeout,

&nbsp;       )

&nbsp;       text = getattr(tr, "text", "") or ""

&nbsp;       return text.strip()



&nbsp;   def \_responses\_fallback(

&nbsp;       self,

&nbsp;       audio\_bytes: bytes,

&nbsp;       cfg: STTConfig,

&nbsp;   ) -> str:

&nbsp;       b64 = base64.b64encode(audio\_bytes).decode("ascii")

&nbsp;       system\_prompt = (

&nbsp;           f"Transcribe the following audio into {cfg.target\_lang} text. "

&nbsp;           "Keep punctuation natural. Do not translate."

&nbsp;       )

&nbsp;       if cfg.prompt:

&nbsp;           system\_prompt += f"\\nContext hint: {cfg.prompt}"



&nbsp;       resp = self.\_client.responses.create(

&nbsp;           model=os.getenv("OPENAI\_STT\_FALLBACK\_MODEL", "gpt-4o-mini-transcribe"),

&nbsp;           input=\[

&nbsp;               {

&nbsp;                   "role": "user",

&nbsp;                   "content": \[

&nbsp;                       {

&nbsp;                           "type": "input\_audio",

&nbsp;                           "audio": {"data": b64, "format": "wav"},

&nbsp;                       },

&nbsp;                       {

&nbsp;                           "type": "input\_text",

&nbsp;                           "text": system\_prompt,

&nbsp;                       },

&nbsp;                   ],

&nbsp;               }

&nbsp;           ],

&nbsp;           timeout=cfg.timeout,

&nbsp;       )

&nbsp;       # 這段擷取 output\_text 的寫法，延續你原有的實作。:contentReference\[oaicite:13]{index=13}

&nbsp;       if hasattr(resp, "output\_text") and resp.output\_text:

&nbsp;           return resp.output\_text.strip()



&nbsp;       for out in getattr(resp, "output", \[]):

&nbsp;           if out.get("type") == "message":

&nbsp;               for c in out.get("content", \[]):

&nbsp;                   if c.get("type") == "output\_text":

&nbsp;                       return (c.get("text") or "").strip()

&nbsp;       return ""



&nbsp;   def transcribe(

&nbsp;       self,

&nbsp;       audio\_bytes: bytes,

&nbsp;       mime\_type: str = "audio/wav",

&nbsp;       config: Optional\[STTConfig] = None,

&nbsp;   ) -> str:

&nbsp;       cfg = config or STTConfig()

&nbsp;       # 先試 Whisper

&nbsp;       try:

&nbsp;           text = self.\_whisper(audio\_bytes, mime\_type, cfg)

&nbsp;           if text:

&nbsp;               return text

&nbsp;       except Exception as e:

&nbsp;           print(f"\[whisper\_error] {e}")



&nbsp;       # Whisper 失敗 → Responses fallback

&nbsp;       try:

&nbsp;           text = self.\_responses\_fallback(audio\_bytes, cfg)

&nbsp;           if text:

&nbsp;               return text

&nbsp;       except Exception as e:

&nbsp;           print(f"\[stt\_fallback\_error] {e}")



&nbsp;       return ""

```



\### 4.3 STT 使用範例



```python

\# example\_stt.py

from pathlib import Path

from app.services.openai\_stt\_client import OpenAIWhisperSTTClient, STTConfig



def main():

&nbsp;   client = OpenAIWhisperSTTClient()

&nbsp;   audio = Path("sample.wav").read\_bytes()



&nbsp;   text = client.transcribe(

&nbsp;       audio,

&nbsp;       mime\_type="audio/wav",

&nbsp;       config=STTConfig(

&nbsp;           target\_lang="zh-TW",

&nbsp;           prompt="產品內部評估會議記錄，充滿專有名詞，請盡量保留原始發音。",

&nbsp;       ),

&nbsp;   )

&nbsp;   print(text)



if \_\_name\_\_ == "\_\_main\_\_":

&nbsp;   main()

```



---



\## 5. Text-to-Image（T2I）：NanoBanana 建議寫法



雖然 OpenAI 本身也能透過 Responses + image tool 生圖，(\[OpenAI Platform]\[5])

但你這邊決策是「生圖一律走 NanoBanana / Gemini」，這很合理──

\*\*對話模型專心理解 / 控制邏輯，圖像模型專心出圖。\*\*



\### 5.1 通用 ImageClient 介面（T2I / I2I 共用）



```python

\# image\_client.py

from dataclasses import dataclass

from typing import List, Dict, Generator, Optional



@dataclass

class ImageGenConfig:

&nbsp;   aspect\_ratio: str = "16:9"

&nbsp;   style\_hint: Optional\[str] = None

&nbsp;   no\_text: bool = True

&nbsp;   timeout: float = 60.0



class ImageClient:

&nbsp;   def generate\_from\_text(

&nbsp;       self,

&nbsp;       prompt: str,

&nbsp;       config: Optional\[ImageGenConfig] = None,

&nbsp;   ) -> List\[str]:

&nbsp;       raise NotImplementedError



&nbsp;   def stream\_from\_text(

&nbsp;       self,

&nbsp;       prompt: str,

&nbsp;       config: Optional\[ImageGenConfig] = None,

&nbsp;   ) -> Generator\[Dict, None, None]:

&nbsp;       raise NotImplementedError



&nbsp;   def generate\_from\_images(

&nbsp;       self,

&nbsp;       prompt: str,

&nbsp;       images: List\[bytes],

&nbsp;       mimes: List\[str],

&nbsp;       config: Optional\[ImageGenConfig] = None,

&nbsp;   ) -> List\[str]:

&nbsp;       raise NotImplementedError



&nbsp;   def stream\_from\_images(

&nbsp;       self,

&nbsp;       prompt: str,

&nbsp;       images: List\[bytes],

&nbsp;       mimes: List\[str],

&nbsp;       config: Optional\[ImageGenConfig] = None,

&nbsp;   ) -> Generator\[Dict, None, None]:

&nbsp;       raise NotImplementedError

```



事件格式建議沿用你現在的 NanoBanana 寫法：



\* `{"event": "status", "text": "..."}`

\* `{"event": "image\_chunk\_saved", "path": "..."}`

\* `{"event": "error", "message": "..."}`

\* `{"event": "completed", "images": \["..."]}`



---



\### 5.2 NanoBanana T2I 實作



以下把你現在 `NanoBananaImageGen` 稍微 generalize 成 `NanoBananaImageClient`。



```python

\# nanobanana\_client.py

from typing import List, Dict, Generator, Optional

from pathlib import Path

import mimetypes

import os



from google import genai

from google.genai import types



from .image\_client import ImageClient, ImageGenConfig



ASSETS\_DIR = Path(\_\_file\_\_).resolve().parents\[1] / "assets"

GALLERY\_DIR = ASSETS\_DIR / "gallery"

GALLERY\_DIR.mkdir(parents=True, exist\_ok=True)



def \_elder\_style\_hint() -> str:

&nbsp;   return (

&nbsp;       "Taiwanese elder-meme aesthetic: warm colors, sentimental composition, "

&nbsp;       "slightly kitsch, full of positivity."

&nbsp;   )



def \_no\_text\_guardrail\_hint() -> str:

&nbsp;   return (

&nbsp;       "Render an aesthetically pleasing image with NO visible text, NO letters, "

&nbsp;       "NO watermarks, and NO typographic elements. Typography-free."

&nbsp;   )



def \_safe\_filename(stem: str, ext: str) -> Path:

&nbsp;   stem = "".join(c if c.isalnum() or c in "-\_." else "\_" for c in stem)\[:64]

&nbsp;   return (GALLERY\_DIR / f"{stem}{ext}").resolve()





class NanoBananaImageClient(ImageClient):

&nbsp;   def \_\_init\_\_(self, model: Optional\[str] = None):

&nbsp;       key = os.environ.get("GEMINI\_API\_KEY")

&nbsp;       if not key:

&nbsp;           raise RuntimeError("GEMINI\_API\_KEY 未設定")

&nbsp;       self.\_client = genai.Client(api\_key=key)

&nbsp;       self.\_model = model or os.getenv(

&nbsp;           "NB\_IMAGE\_MODEL",

&nbsp;           "gemini-3.1-flash-image-preview",

&nbsp;       )



&nbsp;   # ---- T2I ----

&nbsp;   def stream\_from\_text(

&nbsp;       self,

&nbsp;       prompt: str,

&nbsp;       config: Optional\[ImageGenConfig] = None,

&nbsp;   ) -> Generator\[Dict, None, None]:

&nbsp;       cfg = config or ImageGenConfig()



&nbsp;       full\_prompt = prompt

&nbsp;       if cfg.style\_hint:

&nbsp;           full\_prompt += f"\\n\\nSTYLE: {cfg.style\_hint}"

&nbsp;       full\_prompt += f"\\n\\nPreferred aspect ratio: {cfg.aspect\_ratio}"

&nbsp;       full\_prompt += f"\\n\\n{\_elder\_style\_hint()}"

&nbsp;       if cfg.no\_text:

&nbsp;           full\_prompt += f"\\n\\n{\_no\_text\_guardrail\_hint()}"



&nbsp;       contents = \[

&nbsp;           types.Content(

&nbsp;               role="user",

&nbsp;               parts=\[types.Part.from\_text(text=full\_prompt)],

&nbsp;           )

&nbsp;       ]



&nbsp;       cfg\_gen = types.GenerateContentConfig(

&nbsp;           response\_modalities=\["IMAGE", "TEXT"],

&nbsp;       )



&nbsp;       saved: List\[str] = \[]



&nbsp;       for ch in self.\_client.models.generate\_content\_stream(

&nbsp;           model=self.\_model,

&nbsp;           contents=contents,

&nbsp;           config=cfg\_gen,

&nbsp;       ):

&nbsp;           try:

&nbsp;               if not ch.candidates or not ch.candidates\[0].content:

&nbsp;                   continue

&nbsp;               for part in ch.candidates\[0].content.parts:

&nbsp;                   inline = getattr(part, "inline\_data", None)

&nbsp;                   if inline and inline.data:

&nbsp;                       ext = mimetypes.guess\_extension(inline.mime\_type) or ".png"

&nbsp;                       idx = len(list(GALLERY\_DIR.glob("nb\_t2i\_\*.\*")))

&nbsp;                       path = \_safe\_filename(f"nb\_t2i\_{idx}", ext)

&nbsp;                       with open(path, "wb") as f:

&nbsp;                           f.write(inline.data)

&nbsp;                       saved.append(str(path))

&nbsp;                       yield {"event": "image\_chunk\_saved", "path": str(path)}

&nbsp;                   else:

&nbsp;                       if getattr(ch, "text", ""):

&nbsp;                           yield {"event": "status", "text": ch.text}

&nbsp;           except Exception as e:

&nbsp;               yield {"event": "error", "message": str(e)}



&nbsp;       yield {"event": "completed", "images": saved}



&nbsp;   def generate\_from\_text(

&nbsp;       self,

&nbsp;       prompt: str,

&nbsp;       config: Optional\[ImageGenConfig] = None,

&nbsp;   ) -> List\[str]:

&nbsp;       images: List\[str] = \[]

&nbsp;       for event in self.stream\_from\_text(prompt, config=config):

&nbsp;           if event\["event"] == "image\_chunk\_saved":

&nbsp;               images.append(event\["path"])

&nbsp;           elif event\["event"] == "completed":

&nbsp;               images = event.get("images", images)

&nbsp;       return images



&nbsp;   # I2I 的實作放在下一節

```



---



\### 5.3 T2I 使用範例



```python

\# example\_t2i.py

from app.services.nanobanana\_client import NanoBananaImageClient, ImageGenConfig



def main():

&nbsp;   client = NanoBananaImageClient()



&nbsp;   prompt = "夕陽下三代同堂在客廳聊天吃水果，暖色調，像洗照片店的宣傳照片。"

&nbsp;   cfg = ImageGenConfig(

&nbsp;       aspect\_ratio="16:9",

&nbsp;       style\_hint="Soft lighting, candid family photo, nostalgic color grading.",

&nbsp;       no\_text=True,

&nbsp;   )



&nbsp;   print("=== Streaming ===")

&nbsp;   for event in client.stream\_from\_text(prompt, config=cfg):

&nbsp;       et = event\["event"]

&nbsp;       if et == "status":

&nbsp;           print("\[STATUS]", event\["text"])

&nbsp;       elif et == "image\_chunk\_saved":

&nbsp;           print("\[IMAGE]", event\["path"])

&nbsp;       elif et == "error":

&nbsp;           print("\[ERROR]", event\["message"])

&nbsp;       elif et == "completed":

&nbsp;           print("\[DONE]", event\["images"])



if \_\_name\_\_ == "\_\_main\_\_":

&nbsp;   main()

```



---



\## 6. Image-to-Image（I2I）：NanoBanana 合成 / 變身



I2I 在概念上就是：

\*\*多加幾個參考圖片的 bytes + 強調「保持臉」的 system instruction\*\*。

你現在的 NanoBanana 版本已經這樣做了：

\* 每張圖前面都有一段文字解釋這是誰的臉

\* system instruction 強調「不要發明新臉、保持人數、膚色、年齡感」

\### 6.1 I2I 內容建構 helper



```python

\# nanobanana\_client.py (續)

from google.genai import types



def \_system\_instruction\_i2i() -> str:

&nbsp;   return (

&nbsp;       "You are an image editor for family portraits. "

&nbsp;       "STRICT REQUIREMENT: Preserve the identities and facial features of the people "

&nbsp;       "in the input reference photos. Do NOT invent new faces. "

&nbsp;       "Keep the same people count, age cues, skin tone, and relative facial proportions. "

&nbsp;       "Clothing, accessories, hairstyle, and full scene may change to match the theme. "

&nbsp;       "Place the family together in one coherent frame unless the prompt explicitly asks otherwise. "

&nbsp;       "Never render any visible text or letters in the image."

&nbsp;   )



def \_build\_i2i\_contents(

&nbsp;   prompt: str,

&nbsp;   images: List\[bytes],

&nbsp;   mimes: List\[str],

) -> List\[types.Content]:

&nbsp;   labels = \["GRANDPARENT", "GRANDCHILD"]

&nbsp;   contents: List\[types.Content] = \[]



&nbsp;   for idx, (buf, mt) in enumerate(zip(images, mimes)):

&nbsp;       tag = labels\[idx] if idx < len(labels) else f"PHOTO\_{idx+1}"

&nbsp;       parts = \[

&nbsp;           types.Part.from\_text(

&nbsp;               text=(

&nbsp;                   f"PHOTO\_{idx+1} = {tag}. "

&nbsp;                   f"This is the {tag.lower()} face reference. "

&nbsp;                   "Keep identity and facial structure unchanged."

&nbsp;               )

&nbsp;           ),

&nbsp;           types.Part.from\_bytes(mime\_type=mt, data=buf),

&nbsp;       ]

&nbsp;       contents.append(types.Content(role="user", parts=parts))



&nbsp;   final\_text = (

&nbsp;       f"THEME: {prompt}\\n\\n"

&nbsp;       f"{\_elder\_style\_hint()}\\n\\n"

&nbsp;       f"{\_no\_text\_guardrail\_hint()}\\n\\n"

&nbsp;       "Keep facial identities from the provided references, but restyle clothing and background to fit the theme. "

&nbsp;       "Compose a joyful, flattering family scene."

&nbsp;   )

&nbsp;   contents.append(

&nbsp;       types.Content(role="user", parts=\[types.Part.from\_text(text=final\_text)])

&nbsp;   )

&nbsp;   return contents

```



\### 6.2 NanoBanana I2I streaming 實作



```python

\# nanobanana\_client.py (續)

from typing import List, Dict, Generator, Optional



class NanoBananaImageClient(ImageClient):

&nbsp;   # ...前面的 \_\_init\_\_ / T2I 省略...



&nbsp;   def stream\_from\_images(

&nbsp;       self,

&nbsp;       prompt: str,

&nbsp;       images: List\[bytes],

&nbsp;       mimes: List\[str],

&nbsp;       config: Optional\[ImageGenConfig] = None,

&nbsp;   ) -> Generator\[Dict, None, None]:

&nbsp;       cfg = config or ImageGenConfig()

&nbsp;       contents = \_build\_i2i\_contents(prompt, images, mimes)



&nbsp;       cfg\_gen = types.GenerateContentConfig(

&nbsp;           response\_modalities=\["IMAGE", "TEXT"],

&nbsp;           system\_instruction=types.Content(

&nbsp;               role="user",

&nbsp;               parts=\[types.Part.from\_text(text=\_system\_instruction\_i2i())],

&nbsp;           ),

&nbsp;       )



&nbsp;       saved: List\[str] = \[]

&nbsp;       for ch in self.\_client.models.generate\_content\_stream(

&nbsp;           model=self.\_model,

&nbsp;           contents=contents,

&nbsp;           config=cfg\_gen,

&nbsp;       ):

&nbsp;           try:

&nbsp;               if not ch.candidates or not ch.candidates\[0].content:

&nbsp;                   continue

&nbsp;               for part in ch.candidates\[0].content.parts:

&nbsp;                   inline = getattr(part, "inline\_data", None)

&nbsp;                   if inline and inline.data:

&nbsp;                       ext = mimetypes.guess\_extension(inline.mime\_type) or ".png"

&nbsp;                       idx = len(list(GALLERY\_DIR.glob("nb\_i2i\_\*.\*")))

&nbsp;                       path = \_safe\_filename(f"nb\_i2i\_{idx}", ext)

&nbsp;                       with open(path, "wb") as f:

&nbsp;                           f.write(inline.data)

&nbsp;                       saved.append(str(path))

&nbsp;                       yield {"event": "image\_chunk\_saved", "path": str(path)}

&nbsp;                   else:

&nbsp;                       if getattr(ch, "text", ""):

&nbsp;                           yield {"event": "status", "text": ch.text}

&nbsp;           except Exception as e:

&nbsp;               yield {"event": "error", "message": str(e)}



&nbsp;       yield {"event": "completed", "images": saved}



&nbsp;   def generate\_from\_images(

&nbsp;       self,

&nbsp;       prompt: str,

&nbsp;       images: List\[bytes],

&nbsp;       mimes: List\[str],

&nbsp;       config: Optional\[ImageGenConfig] = None,

&nbsp;   ) -> List\[str]:

&nbsp;       images\_out: List\[str] = \[]

&nbsp;       for event in self.stream\_from\_images(prompt, images, mimes, config=config):

&nbsp;           if event\["event"] == "image\_chunk\_saved":

&nbsp;               images\_out.append(event\["path"])

&nbsp;           elif event\["event"] == "completed":

&nbsp;               images\_out = event.get("images", images\_out)

&nbsp;       return images\_out

```



\### 6.3 I2I 使用範例



```python

\# example\_i2i.py

from pathlib import Path

from app.services.nanobanana\_client import NanoBananaImageClient, ImageGenConfig



def main():

&nbsp;   client = NanoBananaImageClient()



&nbsp;   gparent = Path("assets/input/grandparent.jpg").read\_bytes()

&nbsp;   gchild = Path("assets/input/grandchild.jpg").read\_bytes()



&nbsp;   images = \[gparent, gchild]

&nbsp;   mimes = \["image/jpeg", "image/jpeg"]



&nbsp;   prompt = "在宮廟前拍攝的全家福長輩圖，金色光線、喜氣洋洋。"

&nbsp;   cfg = ImageGenConfig(aspect\_ratio="4:3", no\_text=True)



&nbsp;   for event in client.stream\_from\_images(prompt, images, mimes, config=cfg):

&nbsp;       et = event\["event"]

&nbsp;       if et == "status":

&nbsp;           print("\[STATUS]", event\["text"])

&nbsp;       elif et == "image\_chunk\_saved":

&nbsp;           print("\[IMAGE]", event\["path"])

&nbsp;       elif et == "error":

&nbsp;           print("\[ERROR]", event\["message"])

&nbsp;       elif et == "completed":

&nbsp;           print("\[DONE]", event\["images"])



if \_\_name\_\_ == "\_\_main\_\_":

&nbsp;   main()

```



\[1]: https://platform.openai.com/docs/models?utm\_source=chatgpt.com "Models - OpenAI API"

\[2]: https://platform.openai.com/docs/guides/streaming-responses?utm\_source=chatgpt.com "Streaming API responses"

\[3]: https://platform.openai.com/docs/guides/migrate-to-responses?utm\_source=chatgpt.com "Migrate to the Responses API"

\[4]: https://platform.openai.com/docs/guides/images-vision?utm\_source=chatgpt.com "Images and vision - OpenAI API"

\[5]: https://platform.openai.com/docs/guides/image-generation?utm\_source=chatgpt.com "Image generation - OpenAI API"



