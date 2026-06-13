from __future__ import annotations

import textwrap
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report"
FIG = REPORT / "figures"
DATA = REPORT / "data"
OUTPDF = REPORT / "WelfareABM_report.pdf"
OUTMD = REPORT / "WelfareABM_report.md"
OUTPOSTER = REPORT / "WelfareABM_poster.pdf"
COMIC_FONT = Path("/work/home/cryoem666/xyf/temp/pycharm/OPUS-BioLLM-CSTP/font/Comic-Sans-MS-Regular-2.ttf")
CN_FONT = Path("/work/home/cryoem666/xyf/temp/pycharm/llm_study/八股/fonts/TsangerJinKai03-W03.ttf")


def setup_fonts(use_comic: bool = False) -> tuple[str, str]:
    if use_comic and COMIC_FONT.exists():
        pdfmetrics.registerFont(TTFont("ComicCustom", str(COMIC_FONT)))
        return "ComicCustom", "ComicCustom"
    if CN_FONT.exists():
        pdfmetrics.registerFont(TTFont("CN", str(CN_FONT)))
        return "CN", "CN"
    return "Helvetica", "Helvetica-Bold"


def ensure_comic_font() -> str:
    if COMIC_FONT.exists():
        try:
            pdfmetrics.registerFont(TTFont("ComicCustom", str(COMIC_FONT)))
        except Exception:
            pass
        return "ComicCustom"
    return "Helvetica"


def styles(font: str, bold: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName=bold,
            fontSize=22,
            leading=30,
            alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName=font,
            fontSize=13,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName=bold,
            fontSize=16,
            leading=22,
            spaceBefore=10,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName=bold,
            fontSize=13,
            leading=18,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName=font,
            fontSize=10.5,
            leading=17,
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["BodyText"],
            fontName=font,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#444444"),
            spaceBefore=3,
            spaceAfter=9,
        ),
    }


def p(text: str, st: ParagraphStyle) -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), st)


def fig(path: str, width: float, caption: str, st: dict[str, ParagraphStyle], max_height: float = 10 * cm):
    img = Image(str(FIG / path))
    img._restrictSize(width, max_height)
    return [img, p(caption, st["caption"])]


def summary_table(st: dict[str, ParagraphStyle]) -> Table:
    comic = ensure_comic_font()
    df = pd.read_csv(DATA / "multi_seed_summary.csv")
    order = ["No welfare", "UBI only", "Targeted only", "Mixed, 5% error", "Mixed, 15% error"]
    df["policy"] = pd.Categorical(df["policy"], categories=order, ordered=True)
    df = df.sort_values("policy")
    rows = [["Policy", "Asset Gini", "Poverty", "Unemp.", "Treasury(M)", "Avg deficit"]]
    for _, r in df.iterrows():
        rows.append(
            [
                r["policy"],
                f'{r["gini_assets_mean"]:.3f}±{r["gini_assets_std"]:.3f}',
                f'{r["means_tested_poverty_rate_mean"]:.3f}',
                f'{r["unemployment_rate_mean"]:.3f}',
                f'{r["treasury_mean"]/1e6:.2f}',
                f'{r["avg_deficit_last20_mean"]/1e3:.1f}k',
            ]
        )
    table = Table(rows, colWidths=[3.35 * cm, 2.5 * cm, 2.2 * cm, 2.0 * cm, 2.4 * cm, 2.4 * cm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), comic),
                ("FONTSIZE", (0, 0), (-1, -1), 8.6),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAECEF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8B8B8")),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
            ]
        )
    )
    return table


def simple_table(rows: list[list[str]], col_widths: list[float], st: dict[str, ParagraphStyle]) -> Table:
    font = st["body"].fontName
    header_style = ParagraphStyle(
        "table_header",
        parent=st["body"],
        fontName=font,
        fontSize=8.0,
        leading=10,
        alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle(
        "table_cell",
        parent=st["body"],
        fontName=font,
        fontSize=7.3,
        leading=9.3,
        alignment=0,
    )
    wrapped_rows = [
        [
            Paragraph(str(cell).replace("\n", "<br/>"), header_style if row_idx == 0 else cell_style)
            for cell in row
        ]
        for row_idx, row in enumerate(rows)
    ]
    table = Table(wrapped_rows, colWidths=col_widths, repeatRows=1, splitByRow=True)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("FONTSIZE", (0, 0), (-1, -1), 7.3),
                ("LEADING", (0, 0), (-1, -1), 9.3),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAECEF")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8B8B8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def architecture_table(st: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ["文件/模块", "实现内容", "在研究中的作用"],
        ["welfare_abm/config.py", "ModelConfig 与 SubsidyTier，集中管理税率、UBI、补贴档位、人口生命周期、消费和资产下限。", "保证实验参数可复现，并允许政策场景快速切换。"],
        ["welfare_abm/agents.py", "HouseholdAgent、FirmAgent、GovernmentAgent 三类主体及其行为规则。", "承载 ABM 的微观机制：劳动、税收、福利、消费、企业景气和生命周期。"],
        ["welfare_abm/model.py", "WelfareModel 创建主体、组织 step 顺序，并用 Mesa DataCollector 采集指标。", "把微观 Agent 行为连接为社会层面的动态系统。"],
        ["scripts/*.py", "批量实验、政策对比、科研图表、资产流向图和 PDF 报告生成。", "把仿真输出转化为可复现数据、图表和最终报告。"],
        ["app_streamlit.py", "交互式仪表盘，可调税率、UBI、误差率、家庭和企业数量。", "用于参数敏感性探索和课堂演示。"],
    ]
    return simple_table(rows, [4.0 * cm, 6.3 * cm, 6.3 * cm], st)


def agent_design_table(st: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ["Agent", "核心状态变量", "每期行为", "对应 PPT 需求"],
        ["GovernmentAgent", "财政余额、税收收入、UBI 支出、精准补贴支出、骗保支出、漏保金额。", "征收家庭所得税和企业所得税；发放普惠福利；按贫困评分发放精准补贴；记录骗保和漏保。", "政府作为独立主体；普惠福利；精准滴灌；5% 识别误差。"],
        ["FirmAgent", "景气状态、基础工资、岗位容量、工资总额、利润、企业税、雇员列表。", "五状态 Markov 景气转移；根据景气调整工资、收入和岗位容量；用生产率加权随机匹配招聘，避免低生产率者被系统性排除；缴纳企业税。", "3-5 家企业；行情变好或变坏；工资升降；扩招或裁员。"],
        ["HouseholdAgent", "家庭类型、年龄、成人数、孩子数、残疾成人数、资产、生产率、工资收入、福利、消费。", "提供劳动力；收工资；缴税；领取 UBI/精准补贴；消费并更新资产；按季度换算年度死亡风险；成家、孩子成年分家、劳动能力冲击。", "多类家庭；收入花费不同；生命周期演化；无劳动能力家庭；孩子长大。"],
    ]
    return simple_table(rows, [2.7 * cm, 4.8 * cm, 5.6 * cm, 3.6 * cm], st)


def step_table(st: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ["顺序", "代码位置", "仿真动作", "经济含义"],
        ["1", "WelfareModel.step()", "政府、家庭重置本期变量；企业更新景气状态。", "进入新的季度，清空当期工资、税收、福利、消费等流量。"],
        ["2", "HouseholdAgent.labor_offer()", "有劳动能力且未退休的家庭形成劳动供给。", "家庭进入劳动市场。"],
        ["3", "FirmAgent.hire()", "企业按生产率排序招聘，工资受企业景气和个人 productivity 影响。", "企业行情决定就业和工资分配。"],
        ["4", "GovernmentAgent.collect_taxes()", "家庭按工资缴纳所得税，企业按利润缴纳企业税。", "财政收入从家庭和企业流入政府。"],
        ["5", "pay_universal_basic_income()", "家庭按成年人数领取 UBI，儿童不单独领取。", "普惠福利覆盖成年人，避免有孩家庭按儿童数放大财政支出。"],
        ["6", "pay_targeted_subsidies()", "按工资收入和资产折算收入计算贫困评分，按三档发放补贴，同时模拟骗保与漏保。", "精准滴灌与执行误差同时进入模型。"],
        ["7", "HouseholdAgent.consume()", "工资和福利在收到时进入资产；消费阶段只扣除消费支出。", "统一工资和福利的现金流口径，避免福利比工资更“保值”。"],
        ["8", "_lifecycle_update()", "家庭年龄增长、退休、死亡、成家、孩子成年分家、残疾冲击；死亡资产转为遗产、无人继承则归公，负资产由政府核销。", "人口结构和家庭结构随时间内生变化，同时避免资产凭空消失。"],
        ["9", "DataCollector.collect()", "记录 Gini、贫困率、失业率、财政、福利支出、误差金额等指标。", "把微观演化汇总为社会层面结果。"],
    ]
    return simple_table(rows, [1.0 * cm, 3.5 * cm, 6.4 * cm, 5.7 * cm], st)


def build_markdown() -> None:
    summary = pd.read_csv(DATA / "multi_seed_summary.csv")
    key = summary.set_index("policy")
    flows = pd.read_csv(DATA / "asset_flows_summary.csv").set_index("flow")["mean"]
    md = f"""# WelfareABM 最终实验报告

## 摘要

本研究构建了一个基于 Mesa 的福利社会动态演化模型，用多智能体仿真回答“普惠福利、精准滴灌和财政可持续性如何共同影响社会资产流动”的问题。模型借鉴 PolicySpace2 的多主体思想，但去掉空间、房地产、银行和复杂产业网络，保留政府、企业、家庭三类对本题最关键的主体。

代码层面，项目从零实现了 `GovernmentAgent`、`FirmAgent` 和 `HouseholdAgent`。政府执行个人所得税、企业所得税、普惠基本收入和分层精准补贴；企业受五状态 Markov 经济周期影响并调整工资和岗位容量；家庭具有资产、收入、消费、生命周期、劳动能力、成家和孩子成年分家等状态。Mesa 的 `DataCollector` 用于记录资产 Gini、收入 Gini、贫困率、失业率、财政余额、福利支出、骗保支出和漏保金额。

20 个随机种子的稳健性实验表明，混合福利政策最能降低资产不平等。无福利政策的平均资产 Gini 为 {key.loc['No welfare','gini_assets_mean']:.3f}，而混合福利 5% 误差下降到 {key.loc['Mixed, 5% error','gini_assets_mean']:.3f}。其代价是政府财政盈余明显下降，但在校准参数下仍保持正值。

## 建模依据与简化

本模型基于 Agent-Based Modeling 思路：社会总量不是直接设定的，而是由家庭、企业和政府的微观行为逐步涌现。相对于均衡模型，ABM 更适合表达异质家庭、政策执行误差、企业景气波动和生命周期事件。

参考 PolicySpace2 时，本项目保留“家庭—企业—政府”的核心交互，舍弃房地产、地理空间、交通、银行信贷和完整婚配市场。这些模块虽然重要，但会显著提高课程项目的实现复杂度，并稀释本题对福利政策和资产流动的关注。

## 代码实现简介

项目核心目录为 `welfare_abm/`。`config.py` 管理所有参数；`agents.py` 定义三类 Agent；`model.py` 组织每期 step 和数据采集；`metrics.py` 计算 Gini。实验脚本位于 `scripts/`，包括单场景运行、政策比较、多随机种子实验、科研图表生成和最终报告生成。交互式页面由 `app_streamlit.py` 实现。

每个 step 近似一个季度。仿真顺序为：重置本期变量、企业更新景气、家庭提供劳动力、企业招聘和发工资、政府收税、政府发放 UBI、政府发放精准补贴、家庭消费并更新资产、生命周期更新、DataCollector 记录指标。

### 三类 Agent

- `GovernmentAgent`：维护财政余额，征收家庭所得税和企业所得税，发放 UBI 与精准补贴，并记录骗保支出、漏保金额和财政赤字。
- `FirmAgent`：维护企业景气、工资基准、岗位容量、利润和税收。企业景气使用繁荣、稳定、衰退、萧条、复苏五状态 Markov 链，每期影响招聘容量、工资和收入。
- `HouseholdAgent`：维护家庭类型、年龄、成人数、孩子数、劳动能力、资产、生产率、工资收入、福利收入、税收和消费。家庭会年龄增长、退休、死亡、成家、孩子成年分家，也可能受到劳动能力冲击。

### 关键实现细节

精准补贴的资格评估使用 `工资收入 + 可用资产折算收入`，而不是只看工资收入。这样可以避免高资产但无工资的老人或无劳动能力家庭自动获得最高补贴。识别误差分为两类：`false_positive_rate` 表示非贫困家庭骗保成功率，`false_negative_rate` 表示贫困家庭漏保率。

本版修正了三个关键机制问题：第一，死亡风险按年度风险设定，但在季度 step 中会换算为季度概率，避免老人过早消失；第二，企业招聘采用生产率加权随机匹配，而不是对劳动者硬排序后只录用最高生产率者；第三，死亡家庭的资产不会凭空消失，正资产进入遗产或归公通道，负资产由政府作为债务核销支出承担。

Mesa 的 `DataCollector` 每期采集资产 Gini、收入 Gini、当期收入贫困率、资产审查贫困率、失业率、劳动参与率、平均工资、政府财政、UBI 支出、精准补贴支出、骗保支出、漏保金额、税收收入和赤字。这样模型行为和统计输出分离，便于后续扩展。

## 实验设置

实验比较五类政策：无福利、纯普惠福利、纯精准补贴、混合福利 5% 误差、混合福利 15% 误差。默认人口规模为 220 个家庭、4 家企业、80 个 step，并在 20 个随机种子上重复。UBI 按成年人数发放，精准补贴采用三档规则，贫困评分由工资收入和可用资产折算收入共同决定，避免只看工资导致高资产老人也获得最高补贴。

## 结果解释

动态曲线显示，无福利政策财政增长最快，但资产 Gini 最高；混合福利政策最能降低资产 Gini，但财政余额增长最慢。政策对比图显示，混合福利 5% 误差的平均资产 Gini 为 {key.loc['Mixed, 5% error','gini_assets_mean']:.3f}，明显低于无福利政策的 {key.loc['No welfare','gini_assets_mean']:.3f}。

识别误差图显示，误差从 5% 增加到 15% 后，骗保支出和漏保金额都会上升。资产流向图进一步显示，在混合福利 5% 误差场景下，最后 20 期平均每期税收约 {flows.loc['tax_revenue']/1000:.1f}k，福利支出约 {flows.loc['welfare_spending']/1000:.1f}k，财政净流入约 {flows.loc['treasury_delta']/1000:+.1f}k。因此当前校准下再分配通道基本闭合，但安全边际较薄。

## 主要结论

1. 混合政策在公平性上最优，但财政成本最高。
2. 纯普惠福利 能改善资产不平等，但效果弱于混合政策。
3. 纯精准补贴财政负担较低，但覆盖面有限，对总体资产分化改善不足。
4. 识别误差主要体现在漏保金额和骗保支出上；从 5% 到 15% 后，漏保损失明显上升，但宏观 Gini 的变化小于政策组合差异。
5. 资产流向图显示，混合福利 5% 误差场景下最后 20 期平均每期税收约 {flows.loc['tax_revenue']/1000:.1f}k，福利支出约 {flows.loc['welfare_spending']/1000:.1f}k，财政通道小幅正平衡 {flows.loc['treasury_delta']/1000:+.1f}k。
6. 对 PPT 中“公平-效率-财政可持续”的核心问题，当前模型能够给出初步计算实验回答；人口结构反馈与真实校准仍是后续扩展方向。
"""
    OUTMD.write_text(md, encoding="utf-8")


def page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(A4[0] / 2, 1.1 * cm, str(doc.page))
    canvas.restoreState()


def build_pdf() -> None:
    font, bold = setup_fonts(use_comic=False)
    st = styles(font, bold)
    flows = pd.read_csv(DATA / "asset_flows_summary.csv").set_index("flow")["mean"]
    flow_balance_text = "小幅盈余" if flows.loc["treasury_delta"] >= 0 else "小幅赤字"
    doc = SimpleDocTemplate(
        str(OUTPDF),
        pagesize=A4,
        rightMargin=2.1 * cm,
        leftMargin=2.1 * cm,
        topMargin=2.2 * cm,
        bottomMargin=1.8 * cm,
    )
    story = []

    story += [
        Spacer(1, 2.2 * cm),
        p("WelfareABM: 基于多智能体的福利社会动态演化研究", st["title"]),
        p("普惠福利、精准滴灌与财政可持续性的计算实验报告", st["subtitle"]),
        Spacer(1, 1.0 * cm),
        p("课程大作业最终报告", st["subtitle"]),
        Spacer(1, 0.6 * cm),
        p("模型框架：Mesa / Agent-Based Modeling", st["subtitle"]),
        p("实验版本：20 个随机种子的稳健性比较", st["subtitle"]),
        Spacer(1, 5.5 * cm),
        p("2026 年 6 月", st["subtitle"]),
        PageBreak(),
    ]

    story += [
        p("1 研究问题与模型概述", st["h1"]),
        p(
            "本项目围绕“福利政策如何影响社会资产流动”这一核心问题展开。前期 PPT 给出的设定包含一个执行福利政策的政府、"
            "若干行情波动的企业，以及大量收入、消费、年龄、劳动能力和家庭结构不同的家庭。为了把这些需求转化为可计算实验，"
            "本报告采用多智能体仿真（Agent-Based Modeling, ABM）方法：不直接假设社会整体结果，而是让政府、企业和家庭在每个时间步"
            "根据规则交互，再观察资产分配、贫困率、失业率和财政余额如何从微观行为中涌现。",
            st["body"],
        ),
        p(
            "ABM 的优势在于可以自然表达异质性和非均衡过程。传统宏观模型通常需要先设定代表性家庭或均衡方程，"
            "而本题中的关键现象恰好来自个体差异：有人可能漏保，有人可能骗保；有些家庭有劳动能力，有些家庭没有；"
            "企业景气会随机变化，家庭生命周期也会改变劳动供给和消费需求。因此，Mesa 框架比直接写一个总量方程更适合本课程项目。",
            st["body"],
        ),
        p(
            "本模型不是对真实国家福利系统的预测模型，而是一个机制型计算沙盘。它的目标是回答方向性问题：在给定税率、UBI、精准补贴档位和识别误差下，"
            "福利政策是否能够降低资产不平等？政府财政是否还能闭合？资源是否真正流向低收入或弱劳动能力家庭？这些问题可以通过多场景仿真和多随机种子重复实验得到初步回答。",
            st["body"],
        ),
        p("2 建模依据与需求取舍", st["h1"]),
        p(
            "模型设计借鉴了 PolicySpace2 的思想，即用家庭、企业、政府等主体构成一个局部经济系统，再通过时间推进观察宏观指标。"
            "但 PolicySpace2 还包含空间地理、房地产、交通、企业网络、财政制度等较重模块。对于本题而言，最核心的问题是福利政策如何通过税收和转移支付改变家庭资产，"
            "因此本项目保留“政府—企业—家庭”的主干结构，精简掉空间、房产、银行信贷、商品库存和完整婚配市场。",
            st["body"],
        ),
        p(
            "这种取舍使模型保持可解释性。政府负责政策执行，企业负责劳动市场和工资收入，家庭负责消费、资产积累和生命周期变化。"
            "三类主体之间的主要资金流为：企业向家庭支付工资，家庭和企业向政府缴税，政府向家庭发放 UBI 和精准补贴，家庭再通过消费形成市场需求。"
            "新增的资产流向图正是把这一闭环可视化，从而回应 PPT 中“整个社会的资产流动是否平衡”的问题。",
            st["body"],
        ),
        PageBreak(),
        p("3 代码结构与实现框架", st["h1"]),
        p(
            "项目从零基于 Mesa 实现，而不是直接修改 PolicySpace2。这样做的原因有三点：第一，Mesa 的 Agent、Model 和 DataCollector 抽象足够轻量，"
            "适合课程项目快速迭代；第二，本题的需求集中在福利政策机制，不需要 PolicySpace2 的全部复杂模块；第三，从零实现可以清楚展示每个行为规则和指标的来源，"
            "便于报告解释、调参和后续扩展。",
            st["body"],
        ),
        architecture_table(st),
        p("表 1：项目主要代码模块与研究功能对应关系。", st["caption"]),
        PageBreak(),
        p("4 Agent 设计", st["h1"]),
        p(
            "模型包含政府、企业和家庭三类 Agent。政府是独立 Agent，而不是写在 model.step() 中的过程函数；企业具有景气状态和招聘行为；"
            "家庭是最复杂的主体，既有经济变量，也有生命周期变量。所有主体的本期流量变量都会在 step 开始时重置，因此工资、税收、福利、消费等指标表示当期发生的流量，"
            "资产和财政余额则表示跨期累积的存量。",
            st["body"],
        ),
        agent_design_table(st),
        p("表 2：三类 Agent 的状态变量、行为规则和 PPT 需求映射。", st["caption"]),
        p(
            "精准补贴资格不是只看工资收入，而是使用“工资收入 + 可用资产折算收入”的贫困评分。这样可以避免一个明显问题："
            "老年家庭或无劳动能力家庭工资为 0，但如果它们拥有较高资产，不应自动获得最高档补贴。识别误差被拆成两类："
            "骗保成功表示非贫困家庭错误获得补贴，漏保表示贫困家庭未获得应得补贴。",
            st["body"],
        ),
        p(
            "本版还修正了三个会显著影响结论的机制细节。第一，死亡风险按年度风险设定，但在季度 step 中使用时转换为季度概率，"
            "避免 75 岁左右老人过早消失。第二，企业招聘不再对劳动者按生产率硬排序，而是采用生产率加权随机匹配，"
            "使低生产率家庭仍有就业机会，避免失业和贫困完全机械地落在低生产率者身上。第三，死亡家庭的资产不再凭空消失："
            "正资产优先作为遗产转给其他家庭，无继承人时归入政府财政；负资产则由政府记为债务核销支出。",
            st["body"],
        ),
        PageBreak(),
        p("5 仿真流程与实验设置", st["h1"]),
        p(
            "一个 step 近似表示一个季度，80 个 step 约等于 20 年。这个尺度可以让家庭年龄、退休、死亡、孩子成年和成家机制发生作用，"
            "同时又不会让初始人口结构在很短时间内完全消失。每期仿真严格按照劳动市场、税收、福利、消费、生命周期和数据采集的顺序执行。",
            st["body"],
        ),
        step_table(st),
        p("表 3：WelfareModel.step() 的执行顺序与经济含义。", st["caption"]),
        p(
            "实验比较五类政策：无福利、纯普惠福利、纯精准补贴、混合福利（5% 识别误差）和混合福利（15% 识别误差）。"
            "默认规模为 220 个家庭和 4 家企业，所得税率为 20%，企业税率为 28%，UBI 为每名成年人每期 100，精准补贴三档为 90/60/30。"
            "每个政策场景运行 80 个 step，并用 20 个随机种子重复实验，以降低企业景气、家庭初始资产和生命周期事件带来的偶然性。",
            st["body"],
        ),
        summary_table(st),
        p("表 4：20 个随机种子的最终指标均值。Treasury 表示最终政府财政余额，Avg deficit 表示最后 20 期平均赤字；负值代表财政盈余。", st["caption"]),
        PageBreak(),
    ]

    story += [
        p("6 动态结果", st["h1"]),
        *fig(
            "fig1_dynamic_curves.png",
            17.0 * cm,
            "图 1：不同福利政策下资产 Gini、政府财政与失业率的动态演化。阴影表示关键政策在不同随机种子下的波动。",
            st,
            max_height=8.0 * cm,
        ),
        p(
            "从动态曲线可以看到，无福利情形下政府财政积累最快，但资产不平等也持续上升。"
            "混合福利政策显著压低资产 Gini，但财政余额增长最慢，体现出公平改善与财政空间之间的权衡。"
            "失业率在各政策间差异小于财政与资产分配差异，说明当前模型中就业主要由企业景气和岗位容量决定，"
            "福利政策本身不是失业变化的唯一驱动。",
            st["body"],
        ),
        p(
            "这些曲线由 Mesa DataCollector 自动记录。模型每期采集家庭数量、财政余额、资产 Gini、收入 Gini、收入贫困率、"
            "资产审查贫困率、失业率、劳动参与率、平均工资、UBI 支出、精准补贴支出、骗保支出、漏保金额、税收收入和赤字等指标。"
            "这样做的好处是仿真逻辑和统计逻辑分离："
            "Agent 只负责行为，DataCollector 负责把微观状态汇总为宏观时间序列。",
            st["body"],
        ),
        PageBreak(),
        p("7 政策组合比较", st["h1"]),
        *fig(
            "fig2_policy_outcomes.png",
            16.5 * cm,
            "图 2：不同政策的最终资产 Gini 与资产审查贫困率。柱顶为 20 个随机种子的均值，误差线为标准差。",
            st,
            max_height=8.0 * cm,
        ),
        p(
            "混合福利政策在资产 Gini 上表现最好：5% 误差混合政策的平均资产 Gini 为 0.513，显著低于无福利的 0.769。"
            "纯普惠福利 和纯精准补贴都能降低不平等，但效果弱于混合政策。贫困率方面，各政策差异小于 Gini，说明当前参数下"
            "福利政策更直接影响资产缓冲和财富积累，而对贫困线附近家庭的即时收入改善相对有限。",
            st["body"],
        ),
        *fig(
            "fig3_tradeoff.png",
            12.0 * cm,
            "图 3：财政余额与资产 Gini 的权衡。越靠左表示财政空间越小，越靠下表示资产分配越公平。",
            st,
            max_height=7.2 * cm,
        ),
        p(
            "财政-公平散点图进一步表明：无福利位于右上角，财政最宽裕但不平等最高；混合政策位于左下角，"
            "公平性最好但财政空间最紧。纯普惠福利 与纯精准补贴处于中间区域，分别代表较广覆盖与较窄覆盖的两种折中。",
            st["body"],
        ),
        p(
            "从 coding 角度看，政策对比不是手工改参数后单次运行，而是在 `scripts/multi_seed_experiment.py` 中把五种政策写成五组 ModelConfig，"
            "再用同一套 run_case 函数循环 20 个随机种子。每个 case 的末期指标和最后 20 期平均赤字都会写入 CSV，随后绘图脚本读取 CSV 生成图表。"
            "这种设计使报告中的结果可以完全复现，也方便继续增加新政策场景。",
            st["body"],
        ),
        PageBreak(),
    ]

    story += [
        p("8 识别误差与政策执行", st["h1"]),
        *fig(
            "fig4_error_accounting.png",
            13.0 * cm,
            "图 4：精准补贴识别误差的会计分解。False-positive spending 表示骗保导致的错发，False-negative missed aid 表示漏保导致的未发补贴。",
            st,
            max_height=7.6 * cm,
        ),
        p(
            "识别误差对宏观资产 Gini 的影响小于政策组合本身，但对资源流向具有清晰影响。误差从 5% 上升到 15% 后，"
            "漏保导致的未发补贴显著增加，骗保支出也同步上升。这说明在模型中，识别误差首先表现为福利资源配置效率下降，"
            "其次才通过长期资产积累影响宏观不平等。",
            st["body"],
        ),
        p(
            "在实现上，精准补贴先根据真实贫困评分得到 true_amount，然后再引入执行误差。若家庭本应获得补贴，则有 false_negative_rate 的概率漏保；"
            "若家庭本不应获得补贴，则有 false_positive_rate 的概率骗保成功，并随机获得某一档补贴。政府 Agent 会同时记录错发金额和未发金额，"
            "因此模型不仅能看宏观 Gini，也能追踪政策执行误差本身造成的资源错配。",
            st["body"],
        ),
        PageBreak(),
        p("9 资产流向与系统平衡", st["h1"]),
        *fig(
            "fig5_asset_flow.png",
            17.0 * cm,
            "图 5：混合福利 5% 误差场景下的资产流向图。箭头宽度表示 20 个随机种子最后 20 期的平均货币流量；家庭框中的 net 表示该类家庭当期工资、福利、税收和消费后的净资产变动。",
            st,
            max_height=8.9 * cm,
        ),
        p(
            "资产流向图直接回应了“整个社会的资产流动是否平衡”这一问题。混合福利 5% 误差场景中，"
            f"最后 20 期平均每期税收约 {flows.loc['tax_revenue']/1000:.1f}k，福利支出约 {flows.loc['welfare_spending']/1000:.1f}k，"
            f"财政通道呈现{flow_balance_text}，净额约 {flows.loc['treasury_delta']/1000:+.1f}k。"
            "这说明当前校准下，政府再分配系统没有出现财政坍塌，但安全边际较薄。",
            st["body"],
        ),
        p(
            "从流量结构看，工资和消费仍是最大规模的市场循环，福利转移规模略低于总税收。"
            "因此，混合政策在模型中更像是对市场收入分配的再平衡机制，而不是完全替代工资收入。"
            "若提高 UBI 或扩大精准补贴，图中的政府到家庭箭头会迅速变粗，并可能把财政余额推入赤字。",
            st["body"],
        ),
        p(
            "这张图的数据不是手工填入，而是由 `scripts/asset_flow_figure.py` 重新运行混合福利 5% 误差场景，并汇总 20 个随机种子最后 20 期的平均流量。"
            "脚本读取每个家庭的 wage_income、taxes_paid、ubi_received、targeted_received 和 consumption，同时读取企业的 corporate tax 与政府的总税收和总支出，"
            "最后输出 `asset_flows_summary.csv` 和 `asset_flows_by_household_type.csv`。因此，图中的箭头宽度和数值都来自模型状态本身。",
            st["body"],
        ),
        PageBreak(),
        p("10 对 PPT 研究问题的回答", st["h1"]),
        p(
            "<b>公平与效率：</b>混合政策最能降低资产 Gini，但伴随财政空间下降和略高失业波动；因此公平改善并非免费，"
            "而是以财政资源和市场扰动为代价。",
            st["body"],
        ),
        p(
            "<b>财政可持续性：</b>校准后所有政策均未破产，但混合政策财政余额最低，说明其更接近可持续边界。",
            st["body"],
        ),
        p(
            "<b>识别误差：</b>模型能够量化漏保与骗保金额。识别误差升高会导致错配资源增加，但在当前补贴强度下，"
            "其宏观影响小于是否采用混合福利这一政策组合差异。",
            st["body"],
        ),
        p(
            "<b>资产流动平衡：</b>模型新增的流向图显示，混合福利 5% 误差场景下税收与转移支付在尾段基本平衡，"
            "工资-消费市场循环仍占主导。由此可得到一个条件性结论：在当前税率、UBI 和补贴档位下，社会资产流动"
            "不是绝对均等的，但再分配通道能够缓解资产分化且暂时不破坏财政闭环。",
            st["body"],
        ),
        p(
            "<b>人口结构反馈：</b>模型已包含轻量生命周期与家庭形成机制，因此可以观察家庭数、老年家庭、无劳动能力家庭等结构变化。"
            "但婚配、生育和真实人口校准仍为简化处理，因此人口结构结论应作为趋势性结果，而非现实预测。",
            st["body"],
        ),
        p("11 结论、局限与复现方式", st["h1"]),
        p(
            "本研究的核心结论是：在当前 WelfareABM 设定下，普惠福利与精准补贴的混合政策最有利于降低资产不平等；"
            "纯普惠福利 和纯精准补贴均有改善作用，但单独使用时效果有限。混合政策的主要代价是财政空间明显收缩。"
            "识别误差能够通过错发和漏发指标被量化，但若补贴规模较小，其宏观效应需要多随机种子实验才能稳定识别。",
            st["body"],
        ),
        p(
            "模型仍有三点局限：第一，企业部门仅以 3-5 家企业和 Markov 景气状态近似真实市场；第二，家庭形成和代际更替仍是规则化简；"
            "第三，贫困线、税率和消费参数尚未用真实数据校准。因此，本报告更适合作为政策机制的计算沙盘，而非现实政策预测。",
            st["body"],
        ),
        p(
            "复现实验时，可在项目根目录依次运行：`python scripts/multi_seed_experiment.py` 生成多随机种子数据，"
            "`python scripts/report_figures.py` 生成四张政策结果图，`python scripts/asset_flow_figure.py` 生成资产流向图，"
            "最后运行 `python scripts/make_report.py` 生成 PDF、Markdown 和海报。若需要交互式探索参数，可运行 `streamlit run app_streamlit.py`。",
            st["body"],
        ),
    ]

    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)


def build_poster() -> None:
    font, bold = setup_fonts(use_comic=True)
    st = styles(font, bold)
    doc = SimpleDocTemplate(
        str(OUTPOSTER),
        pagesize=A4,
        rightMargin=1.1 * cm,
        leftMargin=1.1 * cm,
        topMargin=0.65 * cm,
        bottomMargin=0.55 * cm,
    )
    summary = pd.read_csv(DATA / "multi_seed_summary.csv").set_index("policy")
    headline = (
        f"Mixed policy reduces asset Gini from "
        f"{summary.loc['No welfare','gini_assets_mean']:.3f} to "
        f"{summary.loc['Mixed, 5% error','gini_assets_mean']:.3f}"
    )
    box_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F8FB")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD2DD")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]
    )
    cards = Table(
        [
            [
                p("<b>Question</b><br/>Can UBI and targeted transfers balance fairness and fiscal sustainability?", st["body"]),
                p("<b>Model</b><br/>Government + 3-5 firms + heterogeneous households with lifecycle dynamics.", st["body"]),
            ],
            [
                p("<b>Main finding</b><br/>Mixed welfare produces the strongest reduction in asset inequality.", st["body"]),
                p("<b>Trade-off</b><br/>The same policy consumes the most fiscal space, but remains sustainable after calibration.", st["body"]),
            ],
        ],
        colWidths=[9.0 * cm, 9.0 * cm],
        rowHeights=[1.75 * cm, 1.75 * cm],
    )
    cards.setStyle(box_style)
    story = [
        p("WelfareABM", st["title"]),
        p("A poster-style summary of agent-based welfare policy experiments", st["subtitle"]),
        p(headline, st["subtitle"]),
        Spacer(1, 0.15 * cm),
        cards,
        Spacer(1, 0.15 * cm),
        *fig(
            "fig2_policy_outcomes.png",
            17.0 * cm,
            "Policy comparison over 20 random seeds. Mixed welfare has the lowest asset Gini.",
            st,
            max_height=6.2 * cm,
        ),
        *fig(
            "fig5_asset_flow.png",
            17.0 * cm,
            "Asset-flow balance: tax revenue and transfers are nearly closed in the calibrated mixed policy.",
            st,
            max_height=7.2 * cm,
        ),
    ]
    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)


def main() -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    build_markdown()
    build_pdf()
    build_poster()
    print(f"wrote {OUTPDF}")
    print(f"wrote {OUTPOSTER}")
    print(f"wrote {OUTMD}")


if __name__ == "__main__":
    main()
