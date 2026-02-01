# Amon

* 規格整理：[`SPEC_v1.1.3.md`](SPEC_v1.1.3.md)

## CLI 快速開始

```bash
# 安裝套件
pip install -e .

# 建立專案
amon project create "2026Q1 市場研究"

# 列出專案
amon project list

# 更新專案名稱
amon project update <project_id> --name "新版專案名稱"

# 刪除（移至回收桶）與還原
amon project delete <project_id>
amon project restore <project_id>
```
