# Render 部署说明

## PostgreSQL（Supabase 等）

在 Render 的 **Environment** 中设置：

- `DATABASE_URL`：从 Supabase **Project Settings → Database** 复制 **URI**（建议带 `?sslmode=require`）。

### Render 报错：IPv6 / Network is unreachable

部分云厂商容器**没有 IPv6 出站**，而 DNS 可能解析到 Supabase 的 IPv6，导致：

`connection to server at "2406:...":5432 failed: Network is unreachable`

处理方式（任选其一）：

1. **推荐（代码已支持）**：保持 `DATABASE_URL` 不变，部署包含 `storage.py` 中「IPv4 hostaddr 回退」的版本；首次连接失败时会自动解析 IPv4 并重试。
2. **强制 IPv4**：设置环境变量 `PG_FORCE_IPV4=1`（将**严格**使用 IPv4：若 DNS 无 A 记录会报错并提示改用 Pooler 或 `PG_HOSTADDR`）。
3. **使用 Supabase Connection Pooling（强烈推荐）**：在控制台使用 **Session mode** 的 Pooler 连接串（端口常为 `6543`），主机名与直连 `db.*.supabase.co` 不同，通常可避开纯 IPv6 路径问题。
4. **手动指定 IPv4**：在本机执行 `nslookup db.xxx.supabase.co` 若能看到 IPv4，可在 Render 增加 `PG_HOSTADDR=<该 IPv4>`（与 `DATABASE_URL` 同用）。

### 报错：`urllib.parse` / `_check_bracketed_host` / `ip_address`

若 `DATABASE_URL` 里的**密码含 `@`、`:`、`[` 等字符**，必须用 **URL 百分号编码**（Supabase 控制台「复制连接串」一般已编码）。  
服务端解析 IPv4 回退时使用 `psycopg.conninfo`（与 libpq 一致），**不要**用 `urllib.parse` 拆整段 URI，否则会误把密码当成 host 段触发上述错误。

## 其他

- `DEEPSEEK_API_KEY`：必填（或按 `api_client.py` 说明配置本地 key 文件，不推荐用于生产）。
