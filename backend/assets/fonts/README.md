# 报告中文字体

## 为什么放在仓库里

`backend/app/services/report_service.py` 生成检查报告 PDF 时需要中文字体。
原先只从系统路径（`C:/Windows/Fonts`、`/usr/share/fonts/...`）里找，
服务器上没有装中文字体时就静默回退到 reportlab 内置的 Helvetica —— Helvetica 没有中文字形，
于是导出的 PDF 里中文全部变成黑方块（对应测试问题清单第 11 条）。

现在把字体随代码一起部署：`report_service._init_fonts()` 的第一优先级就是本目录，
服务器不需要额外装字体。

## 文件说明

| 文件 | 说明 |
|------|------|
| `NotoSansSC-Regular.ttf` | Noto Sans SC Regular，由可变字体实例化为静态字重后子集化，约 7.3 MB，22,398 个字形，覆盖 CJK 基本区（含生僻字） |
| `OFL.txt` | SIL Open Font License 1.1 许可证全文 |

**许可**：Noto Sans SC 采用 SIL Open Font License 1.1，允许自由使用、修改、再分发
（包括随商业产品分发），条件是保留版权声明与许可证文本。`OFL.txt` 必须随字体一起保留。

**上游来源**：<https://github.com/google/fonts/tree/main/ofl/notosanssc>

## 为什么需要子集化

上游提供的是可变字体（`NotoSansSC[wght].ttf`，约 17.7 MB）。
reportlab 的 `TTFont` 不支持可变字体，必须先实例化为静态字重；
同时为控制仓库体积，裁掉了报告用不到的字形（日文汉字异体、韩文、Emoji 等），
保留 ASCII、拉丁补充、希腊字母、常用符号、CJK 标点、假名与 **CJK 基本区全量**
（公司名/人名里的生僻字如「喆」「昇」「甯」不会缺字）。

## 如何重新生成

需要 `fonttools`（构建期依赖，不进 `requirements.txt`）：

```bash
pip install "fonttools>=4.50"
python scripts/build_report_font.py
```

脚本会下载上游可变字体、实例化 `wght=400`、子集化并覆盖本目录的 `NotoSansSC-Regular.ttf`。

## 新增中文字体时的注意事项

- 必须是 **TrueType（`glyf` 轮廓）** 字体。CFF/OTF 轮廓（如 `SourceHanSansSC-Regular.otf`）
  reportlab 的 `TTFont` 加载不了。
- `.ttc` 字体集合需要传 `subfontIndex`，`_init_fonts()` 已统一按 `subfontIndex=0` 加载。
- 加完字体后建议跑一次自检，确认能正常嵌入：
  生成任意记录的报告 PDF，PDF 内应出现 `/FontFile2` 对象。
