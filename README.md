# SubQA

**中译英 AI 字幕质检工具。** 不只检查格式，更检查格式检查器发现不了的语义错误：人称性别译错、人名前后不一致、漏译、大模型输出失控；还能对比两版译文，告诉你换了 Prompt 或翻译供应商之后，哪里变好了、哪里变差了。

```text
$ subqa check zh.srt en_ai.srt --glossary glossary.csv
共 8 条字幕：3 个错误，11 个警告

[一致性]
  ✗ 1    人称性别与原文一致（含省略主语时的上文）
  ✗ 1    人名译法前后统一
  ...
问题明细
  警告 #3    原文第 2 条指向女性，译文却用了 he / him / his
         原文：说今晚不回来吃饭了。
         译文：He said he won't be home for dinner tonight.
  警告 #6    人名写法不一致：此处为「Wei Zhang」，第 4 条为「Zhang Wei」
  错误 #7    译文长度是原文的 12 倍，疑似输出失控
  错误 #8    残留未翻译的中文：绝绝子
```

## 为什么做这个

AI 翻译让字幕本地化便宜到了每分钟几块钱，质检却还靠人工一条条看。现有工具各管一段：

| 工具 | 能做 | 做不到 |
|---|---|---|
| Subtitle Edit、[cli-subtitle-linter](https://github.com/yigitkonur/cli-subtitle-linter)、[subfixer](https://github.com/chetan-prime/subfixer) | 单个文件的行长、行数、阅读速度检查与自动修复 | 不对照原文，不管翻得对不对 |
| [SRT-Subtitle-Translator-Validator](https://github.com/VjayC/SRT-Subtitle-Translator-Validator) | LLM 翻译后校验时间轴、字符集 | 只查格式，不查语义 |
| Xbench 等 CAT 质检工具 | 术语一致、漏译 | 不懂字幕，不懂 AI 翻译的典型错误 |

SubQA 专注**中译英**，对照中文原文检查译文，规则来自真实 AI 翻译中出现过的错误（见[来源项目](https://github.com/peiyaoc48-bit/ai-subtitle-test)）。如果你只需要格式自动修复，上面的工具更合适。

## 安装

```bash
pip install git+https://github.com/peiyaoc48-bit/subqa.git
```

需要 Python 3.9+，唯一依赖是 [pysubs2](https://github.com/tkarabela/pysubs2)，支持 SRT、VTT、ASS 格式，自动识别 UTF-8 / GBK 编码。

## 用法

```bash
# 质检一份译文
subqa check zh.srt en.srt
subqa check zh.srt en.srt --glossary glossary.csv          # 加术语表
subqa check zh.srt en.srt --format html -o report.html     # 生成可分享的网页报告
subqa check zh.srt en.srt --format json                    # 给其他程序读

# 对比两版译文：换 Prompt、换模型、换翻译供应商后做回归测试
subqa compare zh.srt en_v1.srt en_v2.srt
```

试试仓库里的示例：

```bash
subqa check examples/zh.srt examples/en_ai.srt --glossary examples/glossary.csv
subqa compare examples/zh.srt examples/en_ai.srt examples/en_fixed.srt
```

### 退出码（用于 CI）

| 退出码 | 含义 |
|---|---|
| 0 | 通过 |
| 1 | `check` 发现错误；`compare` 新版本**新引入**了错误（旧问题没修完不算失败）|
| 2 | 用法错误、文件读不了 |

`--fail-on warning` 让警告也算失败，`--fail-on never` 只出报告不拦截。

## 检查项

| 分组 | 检查项 | 级别 | 说明 |
|---|---|---|---|
| 格式 | structure | 错误 | 条数、时间轴与原文一致 |
| | timing | 错误 / 警告 | 时间轴倒置为错误，与下一条重叠为警告 |
| | tags | 错误 | 斜体等格式标签要保留 |
| 可读性 | lines | 错误 / 警告 | 行数超限为错误，单行字符超限为警告 |
| | cps | 警告 | 阅读速度（字符 / 秒）|
| | duration | 警告 | 显示时间太短 |
| 内容 | empty | 错误 | 译文为空 |
| | untranslated | 错误 | 残留未翻译的中文 |
| | length_ratio | 错误 | 译文长度是原文的 N 倍以上，大模型重复输出失控的典型症状 |
| **一致性** | **pronoun** | 警告 | 原文"她 / 妈妈 / 姐姐"，译文却用 he（或反过来）；原文省略主语时看前两条 |
| | **name** | 警告 | 同一人名写法不一致：Zhang Wei / Wei Zhang / Zhang wei |
| | glossary | 警告 | 术语表里的词没有按约定译法翻译 |

一致性检查用规则实现，不调用大模型，速度快、零成本、结果确定；规则只能发现"可疑"之处，所以标为警告，由人工确认。

### 调整阈值

```bash
subqa check zh.srt en.srt --set max_cps=17 --set max_chars_per_line=37
subqa check zh.srt en.srt --skip cps,duration
```

| 配置项 | 默认值 | 来源 |
|---|---|---|
| max_chars_per_line | 42 | Netflix 拉丁字母语言字幕模板（[Backlot 帮助中心](https://backlothelp.netflix.com/hc/en-us/articles/219375728)）|
| max_lines | 2 | 同上 |
| max_cps | 20 | 成人节目常见取值，儿童节目常用 17；未能在 Netflix 官方页面核实，请对照你所在平台的规范 |
| min_duration_ms | 833 | 常见最短显示时长（5/6 秒）|
| max_length_ratio | 10 | 来源项目中的真实缺陷：62 字的原文被扩写成 528 倍 |

### 术语表

CSV 文件，第一行是表头，多个可接受的译法用 `|` 分隔：

```csv
中文,英文译法
张伟,Zhang Wei
绝绝子,amazing|incredible|awesome
```

## 在 GitHub Actions 中使用

```yaml
- run: pip install git+https://github.com/peiyaoc48-bit/subqa.git
- run: subqa check subs/zh.srt subs/en.srt --glossary subs/glossary.csv --format html -o subqa-report.html
- uses: actions/upload-artifact@v4
  if: always()
  with: { name: subqa-report, path: subqa-report.html }
```

## 开发

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

新增一条检查规则：写一个 `fn(src, tgt, profile, glossary) -> list[Issue]` 函数，加进 `src/subqa/checks.py` 的 `CHECKS`。

## 路线图

- [x] 格式、可读性、内容、一致性检查；SRT / VTT / ASS；HTML / JSON 报告
- [x] 译文版本对比（回归检测）
- [ ] 可选的 AI 抽检：标出疑似误译的条目，并在报告中注明 AI 裁判与人工标注的一致率
- [ ] 网络梗、俗语的字面直译检测
- [ ] 发布到 PyPI

## 许可证

MIT
