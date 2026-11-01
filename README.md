# Netconfig-Rules

将同一服务的多个公开上游清单合并成一个可订阅文件，供 Loon 与 Mihomo 使用。此仓库只含通用公开规则及构建程序，不含代理节点、机场订阅地址、家宽凭证、个人网站例外或客户端主配置。

## 订阅地址

基础地址：`https://raw.githubusercontent.com/kakamisamas/Netconfig-Rules/main/rules/`

| 文件 | 完整上游来源 |
| --- | --- |
| Claude.list | Hex Claude + MetaCubeX anthropic |
| Gemini.list | Hex Gemini + MetaCubeX google-gemini |
| Grok.list | Hex Grok + MetaCubeX xai |
| OpenAI.list | Hex OpenAI |
| Other-AI.list | QuixoticHeart 原生 Loon AI 汇总 |
| Steam.list | blackmatrix7 Steam + MetaCubeX Steam + blackmatrix7 SteamCN |
| Domestic.list | Loyalsoldier/surge-rules 的完整 ruleset/direct.txt |

Loon 将地址写入 `[Remote Rule]`，映射到自己的策略；Mihomo 使用 HTTP rule-provider，`behavior: classical`、`format: text`。规则文件不包含出口策略，不提供节点。

## 更新与完整性

GitHub Actions 按每六小时的计划及手动触发拉取全部上游，先验证所有内容，再合并并一次提交发布。GitHub 的计划任务可能延迟。客户端更新一个订阅文件即可获得该服务所有上游的合并结果，无须因新增规则重发主配置。

仅移除完全重复的规则行，不裁掉关键词、IPv4、IPv6、ASN 或其他已支持的匹配条件。保留上游注释；原始响应保存在 `upstream/`，来源、原始条数、加入条数、类型和哈希保存在 `rules/manifest.json`。遇到新语法、空文件或下载失败时整个更新失败，保留已发布版本，不上传不完整结果。

不同服务之间的顺序和冲突由使用者的主配置决定。完整保留选定上游，不代表覆盖每个未来端点；不通过访问 AI 服务检测规则。Other-AI 的来源保持原选定文件，不在此次聚合中扩大服务范围。

## Steam 的边界

这是完整 Steam 服务规则的合并，不是下载专用清单。将它映射为 DIRECT 会同时影响匹配到的商店、社区等服务，不能宣称自动可靠地区分「下载直连、商店代理」。是否使用统一 Steam 策略组由客户端主配置决定。

## 来源与许可

完整上游地址见 `sources.json`，每个输出保留来源和原始注释。上游材料的权利与许可由各自原作者保留，本仓库不将其重新标记为另一许可证。

- HexTTX/Hex-Clash：上游当前未提供可检测的 LICENSE 文件；保留来源与原文件版权注释。
- MetaCubeX/meta-rules-dat：上游 GPL-3.0，原文见 `licenses/MetaCubeX.txt`。
- QuixoticHeart/rule-set：上游 GPL-3.0，原文见 `licenses/QuixoticHeart.txt`。
- blackmatrix7/ios_rule_script：上游 GPL-2.0，原文见 `licenses/blackmatrix7.txt`。

合并脚本只从 `sources.json` 指定的公开 GitHub 文本文件获取规则，不读取任何私有 Netconfig 设置或节点文件。

## 同源 DNS 分流

`dns/Netconfig-DNS.lpx` 是只有 `[Host]` 的 Loon 插件：国内名单的域名使用腾讯 `https://doh.pub/dns-query`；Claude 完整规则中的域名和关键词使用 Cloudflare `https://1.1.1.1/dns-query`。明确的其他代理域名使用 Cloudflare `https://1.0.0.1/dns-query`，其余域名沿用主配置 DNS。插件不包含节点、出口策略、脚本、MITM 或个人例外。

主配置负责将腾讯 DoH 指向 DIRECT、1.1.1.1 指向个人家宽、默认 Cloudflare 1.0.0.1 指向普通 DNS 代理组；Loon 的加密 DNS 遵循规则、系统 DNS 与查询回落开关仍需在设备设置中确认。不能仅凭插件断言整机没有 DNS 绕行。

Windows/Mihomo 可以让 `rules` 与 `nameserver-policy` 引用同一个 Domestic rule-provider。DNS 策略按 Claude → DNS-Proxy → Domestic 的顺序匹配，默认使用普通境外 DoH。`rules/DNS-Proxy.list` 只包含同一批公开规则明确声明的代理域名条件，不把子域例外扩大到父域，更不能扩大到 `.cn`。Loon 先生成 Claude 和精确的境外 DNS 例外，再保留国内父域映射；相同键只保留较高优先级的服务器。Domestic 原始业务名单不变。IP、ASN、USER-AGENT 不假装是可映射的 DNS 域名条件。

DNS 和业务规则在同一次构建中读取同一份上游快照，一次提交发布。每六小时构建，异常语法、空源、国内名单异常缩减或常用样本回归均使更新失败，保留已发布版本。`dns/manifest.json` 记录输入和输出哈希。客户端仍需成功更新资源；不同文件下载不是原子操作，不保证两次下载之间绝无短暂版本差异。远程插件仍会加载完整映射，不能宣称节省设备内存。

国内上游为 GPL-3.0，许可原文见 `licenses/Loyalsoldier-surge-rules.txt`；DNS 排除来源见 `sources.json` 的 `dns_exclusions`，保留其原始快照与上游版权注释。测试仅使用静态规则，不查询或访问 AI 服务。

2026-11-01 回归保护：保留 `.cn` 国内兜底、微信图片/头像、精确域名不扩大到子域、Claude 映射优先级；代理顶级后缀覆盖国内域名时中止发布。原理参考 [ccc592/loon-dns-rules](https://github.com/ccc592/loon-dns-rules) 的精确例外与失败保留旧版本做法。
