# 文献与软件重叠审查（2026-10-24）

这是一份有范围限制的对比，不能据“未在所读材料找到”证明某功能在全球首创。没有运行POPGym或Memory Gym的学习基线，也没有取得这两个项目开发者的评价。

| 比较项 | MiniGrid / MiniWorld | POPGym | Memory Gym | StateBudget-Nav本地包 |
|---|---|---|---|---|
| 提供部分可观测导航/记忆任务 | 有；模块化环境和Gymnasium API | 有；含Labyrinth Escape/Explore等 | 有；Mystery Path等，有限和endless任务 | 复用MiniGrid，另加机制诊断生成器 |
| 统一记忆模型接口 | 环境软件，非所读论文的主要对象 | 已有forward / initial state API | 提供GRU/Transformer-XL等实现 | frame + bytes + public specification；允许可导入的受信符号插件 |
| 约束容量 | 环境API本身不把agent内存作为预算参数 | 附录A明确全部模型recurrent storage256维；不能说没有公平容量比较 | 包含hidden states、cache和window长度配置 | 显式序列化载荷B字节；控制元数据和表示共享预算 |
| 评估目标 | 通用任务环境与定制性 | 多类POMDP的记忆模型比较 | 逐渐增加记忆需求，比较记忆有效性与学习效果 | 无训练符号控制、表示和实验结论审计 |
| 本文需要的整套诊断 | 不宣称其他项目没有可扩展性 | 所读全文/README未展示“符号载荷逐字节收费＋表示对照＋冻结源码续跑＋重启故障例子”的完整流程 | 所读全文未展示这一完整流程 | 已实现；需以版本化构建和集成检查为证 |

## 证据层级与确切重叠

- **MiniGrid**：Farama官方README已获取，引用为Chevalier-Boisvert等，*Minigrid & Miniworld: Modular & Customizable Reinforcement Learning Environments for Goal-Oriented Tasks*，NeurIPS36，2023。我们复用它的环境和真实遮挡传感器；不把这些贡献归于本工具。
- **POPGym**：ICLR2023全文，正文§3.2（文中检索行368起）描述forward/initial state；附录A（1028行起）明确256维storage。高层“统一接口、公平记忆、记忆导航”已经重叠。本工具不能以这些概念本身主张新颖性。附录还明确参数数量与storage数量不可同时等价，和本工具区分代码/常量、临时内存、持久载荷的动机相关。
- **Memory Gym**：已取JMLR接受稿全文，并以JMLR官方页面确认最终信息：Pleines、Pallasch、Zimmer、Preuss，26(6):1–40，2025，https://jmlr.org/papers/v26/24-0043.html 。包含endless任务、GRU/TrXL、缓存hidden states及窗口；不能称第一套长期记忆基准。
- **经典有限记忆图探索**：Menc等、Sudo等全文已读相关内存模型；节点whiteboard与agent内存分开，不能把其覆盖定理或下界转给本工具总载荷。沿墙、rotor、端口计数和Brent检测都是已有思想。
- **地图压缩**：Nelson/Michael2015仅作者机构摘要及元数据，不称复现。packed/compressed geometry只是强对照，不以通用压缩技巧申报原创算法。
- **SoftwareX先例与模板**：Crossref记录证实MapsHD（10.1016/j.softx.2026.102822）和CacheSim（10.1016/j.softx.2024.102018）属于真实软件/benchmark论文。只确认文章存在和题名，未读到出版商全文，不据此类比保证录用。后来从出版社自有legacyfileshare.elsevier.com取得`softwarex-osp-template.tex`，其明确要求五个主要章节、4000词、公开GitHub及README/Licence.txt，并强调Impact权重。主稿已按这五节整理。出版社当前Guide页面仍403，不能证明旧文件覆盖全部当期要求。

原始返回、所读全文及检索请求记录在review/research/sources/overnight_20261023中。宽泛Crossref检索有大量无关命中，不能视为系统综述或无先例证据。

## 严格判决

**算法论文：不能。** 新候选尚无同时越过新颖性和强对照的证据。

**研究软件论文：可成立的投稿路线，但不能承诺录用或称现已满足学校积分。** 理由是交付对象已经可以与算法胜负分离：一个可安装、可扩展、带真实结论反转例子、冻结实验与故障审计流程的软件。其贡献必须定位为这套可复用流程的实现和用途。单独的bytes接口、单独的重放、单独的压缩地图都太普通，不能作核心创新。若最终仍只对这一个自有小研究有用、外部读者无法复用，审稿人以“研究影响不足”直接拒绝是合理的。

软件路线最重要的证据是让独立wheel重现同一比较，证明隐藏状态检查的检出与漏检边界，并让新控制器无需修改评估器即可加入。独立采用/用户量当前为零，必须如实写为预期用途。代码已公开在 GitHub 并采用 MIT 许可证；带 DOI 的归档和最终作者元数据仍待完成。
