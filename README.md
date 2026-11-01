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
