# Sandbox Runner 維運指南

## 快速啟動

### 方式 A：建議（host process + rootless docker）

```bash
pip install -e .[sandbox-runner]
export AMON_SANDBOX_HOST=0.0.0.0
export AMON_SANDBOX_PORT=8088
# 可選：啟用簡單 API key
export AMON_SANDBOX_API_KEY='change-me'
amon-sandbox-runner
```

> 建議使用 rootless Docker。官方文件：
> - Rootless mode: https://docs.docker.com/engine/security/rootless/
> - Linux post-install（含非 root 使用建議）: https://docs.docker.com/engine/install/linux-postinstall/

#### 方式 A-1：systemd user service（完整範例）

建立 `~/.config/systemd/user/amon-sandbox-runner.service`：

```ini
[Unit]
Description=Amon Sandbox Runner (user)
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/Amon
Environment=AMON_SANDBOX_HOST=127.0.0.1
Environment=AMON_SANDBOX_PORT=8088
Environment=AMON_SANDBOX_IMAGE=amon-sandbox-python:latest
ExecStart=%h/.local/bin/amon-sandbox-runner
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
```

啟用與啟動：

```bash
systemctl --user daemon-reload
systemctl --user enable --now amon-sandbox-runner
systemctl --user status amon-sandbox-runner
```

#### 方式 A-2：一鍵腳本（host process + rootless docker）

可直接使用：`tools/sandbox/setup_rootless_runner.sh`

```bash
bash tools/sandbox/setup_rootless_runner.sh --project-dir "$PWD"
systemctl --user status amon-sandbox-runner
```

### 方式 B：docker-compose（一鍵啟動）

```bash
docker compose -f tools/sandbox/docker-compose.yml up
```

> 這個預設 compose **不會**掛載 `/var/run/docker.sock`。
> 若你確定理解風險、且必須使用 socket 模式，才手動改用：

```bash
docker compose -f tools/sandbox/docker-compose.with-docker-sock.yml up
```

> ⚠️ 高風險警告：掛載 `/var/run/docker.sock` 代表容器內 process 可直接控制 host Docker（透過 Unix socket），在多數部署下可等同主機權限升級。此模式僅建議本機短期除錯，且需顯式 opt-in。

## Amon 端設定

```yaml
sandbox:
  runner:
    base_url: http://127.0.0.1:8088
    timeout_s: 30
    api_key_env: SANDBOX_RUNNER_API_KEY
```

若 runner 設定了 `AMON_SANDBOX_API_KEY`，請在 Amon 端把相同金鑰放到 `SANDBOX_RUNNER_API_KEY` 環境變數。

## Threat Model（威脅模型）

- **不信任輸入**：使用者程式碼與 input_files 視為不可信。
- **執行隔離**：runner 固定使用安全 Docker 參數（`--network none`、`--read-only`、`--cap-drop ALL`、`no-new-privileges` 等）。
- **禁止任意 docker flags**：Amon 與 runner 都不接受 LLM/使用者直接傳入 docker 參數，避免透過旗標繞過隔離。
- **檔案邊界**：只接受相對路徑，拒絕 traversal/symlink，並限制檔案數量與大小。
- **最小憑證暴露**：API key 只走環境變數，不寫入 repo 或 log。

## 限制清單（預設）

- `language` 目前只支援 `python`
- `timeout_s`：1 ~ 120 秒
- code 大小：128 KiB
- input/output 檔案數量：最多 32
- 單檔大小：最多 2 MiB
- input 總大小：最多 8 MiB
- output 總大小：最多 8 MiB

## 結構化日誌

runner 會輸出結構化 JSON log：

- `sandbox.run.start`
  - `request_id` / `job_id` / `timeout_s` / `code_bytes`
- `sandbox.run.finish`
  - `request_id` / `job_id` / `status` / `exit_code` / `timed_out` / `duration_ms`
  - `input_files` / `input_bytes` / `output_files` / `output_bytes`

## 常見錯誤排除

1. **401 unauthorized**
   - runner 設定了 `AMON_SANDBOX_API_KEY`，但 Amon 沒送或送錯。
   - 確認 `sandbox.runner.api_key_env` 指向正確環境變數。

2. **docker permission denied**
   - host process 模式：確認執行者有 docker 權限（rootless / docker group）。
   - compose + docker.sock 模式：確認 `/var/run/docker.sock` 可被容器使用。

3. **rootless docker 問題**
   - 建議先在主機端直接跑 `docker run hello-world` 驗證 rootless 正常。

4. **image pull/build 失敗**
   - 檢查 `AMON_SANDBOX_IMAGE` 是否存在，或先手動 `docker pull` / `docker build`。

5. **input/output 過大**
   - 錯誤訊息若提到檔案數量或大小超限，請分批或壓縮資料。

6. **timeout cleanup**
   - 若看到 `sandbox timeout`，runner 會嘗試 `docker rm -f <container>` 清理；若仍殘留容器可手動清理。
