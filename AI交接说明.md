# CoPaw 二次开发交接说明（给下一个 AI）

## 1. 当前仓库状态（已确认）
- 本地路径：`/Volumes/ydyp/CoPaw`
- 当前分支：`main`
- 当前提交：`62232fb`（二次开发提交）
- 跟踪关系：`main -> origin/main`
- 工作区状态：干净（无未提交改动）

远程配置：
- `origin`: `https://github.com/mailuo007/CoPaw.git`（用户 fork）
- `upstream`: `https://github.com/agentscope-ai/CoPaw.git`（官方主仓库）

分支关系：
- `origin/main` = `62232fb`
- `upstream/main` = `320b525`
- 即：当前本地/用户 fork 在官方最新基础上，多 1 个二开提交。

## 2. 本次已完成的关键操作
1. 将官方仓库从 `origin` 改为 `upstream`。
2. 将用户 fork 配置为新的 `origin`。
3. 提交了本地二次开发改动，后经 rebase 后提交哈希变为 `62232fb`。
4. 推送到用户 fork 的 `main` 成功。

## 3. 二次开发提交内容（`62232fb`）
改动文件：
- `console/src/locales/en.json`
- `console/src/locales/ja.json`
- `console/src/locales/ru.json`
- `console/src/locales/zh.json`
- `console/src/pages/Settings/Models/components/modals/CustomProviderModal.tsx`
- `console/src/pages/Settings/Models/components/modals/ProviderConfigModal.tsx`
- `scripts/start_local.sh`（新增）
- `src/copaw/app/routers/providers.py`
- `src/copaw/providers/openai_provider.py`
- `src/copaw/providers/openai_responses_chat_model.py`（新增）
- `tests/unit/providers/test_openai_provider.py`
- `tests/unit/providers/test_provider_manager.py`
- `启动.md`（新增）

## 4. 本次遇到的问题与处理
### 问题 A：推送认证失败
现象：
- `fatal: could not read Username for 'https://github.com': Device not configured`

原因：
- 本机没有可用 GitHub HTTPS 凭据。

处理：
- 使用 GitHub 用户名 + PAT（Personal Access Token）进行 `git push` 认证。

### 问题 B：SSH 推送不可用
现象：
- `Connection closed by 198.18.0.48 port 22`

原因：
- 当前网络/环境下 SSH 22 不可达。

处理：
- 改回 HTTPS 远程地址，通过 PAT 推送。

### 问题 C：`main -> main (fetch first)` 被拒绝
现象：
- 远端 `origin/main` 比本地更新，无法 fast-forward push。

处理流程：
1. `git fetch origin`
2. `git rebase origin/main`
3. 解决冲突后 `git rebase --continue`
4. `git push -u origin main`

### 问题 D：rebase 冲突
冲突文件：
- `src/copaw/providers/openai_provider.py`

冲突策略：
- 保留二开新增的 `OpenAIResponsesChatModel` 逻辑；
- 同时保留上游的 `TokenRecordingModelWrapper` 包装逻辑；
- 使两边能力共存。

### 问题 E：`rebase --continue` 打开 Vim 卡住
现象：
- 非交互终端下进入编辑器导致超时。

处理：
- 使用非交互方式继续：
```bash
GIT_EDITOR=true git rebase --continue
```

## 5. 后续标准维护流程（建议固定执行）
每次要同步官方并保留二开时：

```bash
cd /Volumes/ydyp/CoPaw
git switch main
git fetch upstream --prune
git fetch origin --prune
git rebase upstream/main
git push origin main
```

若 push 被拒绝（远端有新提交）：

```bash
git fetch origin
git rebase origin/main
git push origin main
```

## 6. 快速检查命令
```bash
git remote -v
git status -sb
git log --oneline --decorate -n 8
git rev-list --left-right --count main...origin/main
git rev-list --left-right --count main...upstream/main
```

## 7. 注意事项
- 不要在有未提交改动时直接拉更新。
- 不要使用破坏性命令（如 `git reset --hard`）处理同步问题。
- 优先使用 `rebase` 保持二开历史线性，便于后续维护。
- 认证建议长期使用 PAT 或配置 `gh auth login`。
