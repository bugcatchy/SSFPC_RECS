# docx_build —— Word 文档生成脚本目录

本目录存放项目阶段性成果综述（Word 版）的生成脚本与 docx-js 运行环境。

## 文件清单

| 文件/目录 | 用途 |
|---|---|
| `create.js` | 综述文档生成脚本（docx-js）。修改内容后重新运行构建命令即可再生成 |
| `node_modules/`、`package.json`、`package-lock.json` | `docx` npm 包及依赖（一次性安装，勿删，删了要重装） |

## 如何重新生成

```bash
python3 "C:\Users\BugCat\AppData\Roaming\kimi-desktop\daimon-share\daimon\runtime\kimi-code\home\plugins\managed\kimi-word\skills\kimi-word\scripts\docx.py" build create.js "C:\Users\BugCat\Desktop\SSFPC电力用户聚类阶段性成果综述.docx"
```

输出路径可换；`build` 会自动跑语法检查 + lint + 生成 + OOXML 验证门。

## 环境说明（2026-09-12 首次搭建）

- Git Bash 的 PATH 里没有 node/npm；用 Kimi 客户端内置的 Node：
  `C:\Users\BugCat\AppData\Local\Programs\Kimi\resources\resources\runtime\node`（npm 用同目录 `npm.cmd`）。
- `docx` npm 包必须装在脚本所在目录（Node 按脚本目录向上解析模块，全局安装不认）。

## 排错记录：TOC 手写 XML 解析 bug（2026-09-12）

**现象**：`ImportedXmlComponent.fromXmlString(...)` 解析手写 TOC 目录域 XML 时报
`Unmatched closing tag: w:sdt`，报错列号总在字符串末尾附近，且与内容长度相关
（2 个中文条目时失败、5 个条目时竟通过），表现为"偶发"。

**排查过程**（dbg1~dbg11，调试脚本已删除）：

1. 二分排除条目内容、属性、`instrText` 指令等嫌疑——逐段单独解析全部通过；
2. 用 proxy 捕获最终拼装的 XML 字符串，确认与单独测试通过的内容逐字节一致，
   但放在完整 create.js 流程里就失败；
3. 结论：docx 库自带的 SAX 解析器对**含多字节中文字符的手写 XML 字符串**
   存在长度/分块相关的解析缺陷，非我方 XML 格式错误。

**最终方案**：放弃手写 TOC XML，改用 docx 库原生组件
`TableOfContents`（目录域，Word/WPS 打开时可右键"更新域"刷新页码）
+ 静态条目列表（`PositionalTab` 右对齐点线前导符，作为不刷新域的查看器的兜底）。

**另外两个容易踩的坑**（同次排查中确认，均为校验门报错信息直接指出的）：

- 数学公式组件（`MathRun`/`MathFraction` 等）**必须包在 `new Math({children: [...]})` 里**，
  不能直接作 `Paragraph` 的子元素（否则报 `m:r: This element is not expected`）；
- `PositionalTab` 也**必须包在 `TextRun` 的 `children` 里**，不能直接作 `Paragraph` 子元素
  （否则报 `w:ptab: This element is not expected`）。

**教训（协作约定补记）**：第三方工具链的隐蔽 bug 不值得深挖——第 2 轮隔离测试失败时
就应转向原生组件方案，而不是继续逐层二分。文档类任务的额度大头在排错与逐页渲染，
不在内容生成。
