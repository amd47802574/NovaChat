"""绘制 NovaChat RAG 主图的 9 节点示意图（白板速记版）。

用法：
    uv run --with pillow python docs/draw_rag_graph.py
输出：
    assets/rag-graph.png
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SCALE = 2  # 2 倍分辨率，便于打印
W, H = 1520, 1460
FONT_REGULAR = "C:/Windows/Fonts/msyh.ttc"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"

BG = "#ffffff"
INK = "#1f2933"
MUTED = "#5b6673"
LANE_DECIDE = "#2563eb"
LANE_LOOP = "#0d9488"
LANE_PARALLEL = "#c2410c"
END_BG = "#eef2f7"

# 节点统一字号与行距（逻辑像素）
F_SIZE = 13
LINE_H = 18
FIELD_H = 16
BAND_H = 30
PAD_TOP = 10
PAD_BOTTOM = 12


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """按像素大小加载微软雅黑字体。"""
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(path, size * SCALE)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt) -> tuple[int, int]:
    """量出文本像素尺寸。"""
    left, top, right, bottom = draw.textbbox((0, 0), text, font=fnt)
    return right - left, bottom - top


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int) -> list[str]:
    """按像素宽度折行（中英文混排，逐字断行）。"""
    lines: list[str] = []
    for raw in text.split("\n"):
        current = ""
        for ch in raw:
            candidate = current + ch
            width, _ = text_size(draw, candidate, fnt)
            if width > max_width and current:
                lines.append(current)
                current = ch
            else:
                current = candidate
        lines.append(current)
    return lines


def measure_box(draw, desc: str, writes: list[str], width: int):
    """预先计算节点内文字排版与所需高度。"""
    body = font(F_SIZE)
    inner = (width - 20) * SCALE
    desc_lines = wrap(draw, desc, body, inner)
    field_lines = [wrap(draw, item, body, inner - 14) for item in writes]
    height = (
        PAD_TOP
        + BAND_H
        + len(desc_lines) * LINE_H
        + 4
        + LINE_H
        + sum(len(lines) * FIELD_H for lines in field_lines)
        + PAD_BOTTOM
    )
    return desc_lines, field_lines, height


def draw_box(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    index: str,
    title: str,
    desc: str,
    writes: list[str],
    color: str,
) -> None:
    """绘制一个节点方框：序号 + 名称 + 说明 + 写出的 State 字段。"""
    x0, y0, x1, y1 = [v * SCALE for v in rect]
    radius = 12 * SCALE
    draw.rounded_rectangle(
        (x0, y0, x1, y1),
        radius=radius,
        fill="#ffffff",
        outline=color,
        width=2 * SCALE,
    )
    draw.rounded_rectangle(
        (x0, y0, x1, y0 + BAND_H * SCALE),
        radius=radius,
        fill=color,
    )
    draw.rectangle((x0, y0 + 18 * SCALE, x1, y0 + BAND_H * SCALE), fill=color)

    badge = font(16, bold=True)
    draw.text((x0 + 10 * SCALE, y0 + 5 * SCALE), index, font=badge, fill="#ffffff")
    draw.text(
        (x0 + 42 * SCALE, y0 + 5 * SCALE),
        title,
        font=font(17, bold=True),
        fill="#ffffff",
    )

    body = font(F_SIZE)
    bold_body = font(F_SIZE, bold=True)
    desc_lines, field_lines, _ = measure_box(draw, desc, writes, rect[2] - rect[0])

    cursor = y0 + (PAD_TOP + BAND_H) * SCALE
    for line in desc_lines:
        draw.text((x0 + 10 * SCALE, cursor), line, font=body, fill=INK)
        cursor += LINE_H * SCALE
    cursor += 4 * SCALE
    draw.text((x0 + 10 * SCALE, cursor), "写：", font=bold_body, fill=color)
    cursor += LINE_H * SCALE
    for lines in field_lines:
        for line in lines:
            draw.text((x0 + 14 * SCALE, cursor), "· " + line, font=body, fill=MUTED)
            cursor += FIELD_H * SCALE


def draw_end(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], label: str = "END") -> None:
    """绘制 END 终止标记。"""
    x0, y0, x1, y1 = [v * SCALE for v in rect]
    draw.rounded_rectangle(
        (x0, y0, x1, y1),
        radius=10 * SCALE,
        fill=END_BG,
        outline="#8c97a5",
        width=2 * SCALE,
    )
    fnt = font(15, bold=True)
    width, height = text_size(draw, label, fnt)
    draw.text(
        ((x0 + x1 - width) / 2, (y0 + y1 - height) / 2 - 2 * SCALE),
        label,
        font=fnt,
        fill=MUTED,
    )


def arrow(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    label: str = "",
    label_pos: tuple[int, int] | None = None,
    dashed: bool = False,
) -> None:
    """绘制折线箭头；dashed 用于「返回上一节点」的反向边。"""
    scaled = [(x * SCALE, y * SCALE) for x, y in points]
    color = "#7c8aa0" if dashed else "#334155"
    width = 2 * SCALE

    for index in range(len(scaled) - 1):
        start, end = scaled[index], scaled[index + 1]
        if dashed:
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = max(abs(dx), abs(dy), 1)
            pos = 0
            while pos < length:
                seg = min(12 * SCALE, length - pos)
                ratio = pos / length
                ratio_end = (pos + seg) / length
                draw.line(
                    (
                        start[0] + dx * ratio,
                        start[1] + dy * ratio,
                        start[0] + dx * ratio_end,
                        start[1] + dy * ratio_end,
                    ),
                    fill=color,
                    width=width,
                )
                pos += 20 * SCALE
        else:
            draw.line((start, end), fill=color, width=width)

    (x1, y1), (x2, y2) = scaled[-2], scaled[-1]
    vx, vy = x2 - x1, y2 - y1
    length = max((vx * vx + vy * vy) ** 0.5, 1)
    ux, uy = vx / length, vy / length
    size = 9 * SCALE
    px, py = -uy, ux
    draw.polygon(
        [
            (x2, y2),
            (x2 - ux * size + px * size * 0.5, y2 - uy * size + py * size * 0.5),
            (x2 - ux * size - px * size * 0.5, y2 - uy * size - py * size * 0.5),
        ],
        fill=color,
    )

    if label:
        fnt = font(12)
        lx, ly = label_pos or (points[-2][0] + 8, points[-2][1] - 22)
        width, _ = text_size(draw, label, fnt)
        draw.rectangle(
            (lx * SCALE, ly * SCALE, (lx + width + 8) * SCALE, (ly + 17) * SCALE),
            fill=BG,
        )
        draw.text((lx * SCALE, ly * SCALE), label, font=fnt, fill=MUTED)


def main() -> None:
    """生成 PNG 示意图。"""
    image = Image.new("RGB", (W * SCALE, H * SCALE), BG)
    draw = ImageDraw.Draw(image)

    # ---- 标题 ----
    draw.text(
        (40 * SCALE, 26 * SCALE),
        "NovaChat RAG 主图 · 9 节点（LangGraph StateGraph）",
        font=font(26, bold=True),
        fill=INK,
    )
    draw.text(
        (40 * SCALE, 64 * SCALE),
        "口诀：决策三兄弟（分 · 拆 · 选） → 纠错四连环（检 · 评 · 改 · 扩） → 并行两兄弟（子 · 合）",
        font=font(14),
        fill=MUTED,
    )

    # ---- 节点定义（先量高度，再定坐标）----
    width = 300
    nodes = {
        "n1": dict(
            x=150, y=140, index="1", title="classify_complexity",
            desc="判问题复杂度：simple / complex",
            writes=["complexity", "complexity_reason"], color=LANE_DECIDE,
        ),
        "n2": dict(
            x=630, y=140, index="2", title="decompose_question",
            desc="复杂问题拆 2-4 个独立子问题",
            writes=["sub_questions"], color=LANE_DECIDE,
        ),
        "n3": dict(
            x=630, y=400, index="3", title="offer_scope_select",
            desc="开放式多方向：先让用户选范围",
            writes=[
                "route = scope_select",
                "retrieval_status = needs_scope_selection",
                "hitl_prompt / hitl_options",
                "docs = [] , context = ''",
            ], color=LANE_DECIDE,
        ),
        "n4": dict(
            x=150, y=400, index="4", title="retrieve_initial",
            desc="初始召回：Milvus 稠密 + BM25 混合检索",
            writes=["query", "docs", "context", "rag_trace"], color=LANE_LOOP,
        ),
        "n5": dict(
            x=150, y=680, index="5", title="grade_documents",
            desc="证据评分 + 路由判定（answer / rewrite / clarify / scope_select / no_knowledge）",
            writes=[
                "route / retrieval_status",
                "evidence_relevance / _answerability",
                "evidence_ambiguity / _confidence",
                "missing_slots / hitl_prompt / hitl_options",
                "不可答时 docs = [] , context = ''",
            ], color=LANE_LOOP,
        ),
        "n6": dict(
            x=150, y=960, index="6", title="rewrite_question",
            desc="改写查询：step_back / hyde / complex",
            writes=[
                "expansion_type",
                "expanded_query",
                "step_back_question / step_back_answer",
                "hypothetical_doc",
                "rewrite_count + 1",
            ], color=LANE_LOOP,
        ),
        "n7": dict(
            x=150, y=1240, index="7", title="retrieve_expanded",
            desc="用扩展查询二次召回并去重重排",
            writes=["docs", "context", "rag_trace"], color=LANE_LOOP,
        ),
        "n8": dict(
            x=1110, y=400, index="8", title="rag_sub_agent",
            desc="每个子问题独立跑一遍 4→5→6→7 子图",
            writes=["sub_results[]（reducer 累加）"], color=LANE_PARALLEL,
        ),
        "n9": dict(
            x=1110, y=680, index="9", title="synthesis",
            desc="合并所有子 Agent 结果，去重 + 重排 rrf_rank",
            writes=[
                "docs / context",
                "route / retrieval_status",
                "hitl_prompt / hitl_options",
                "rag_trace",
            ], color=LANE_PARALLEL,
        ),
    }

    rects: dict[str, tuple[int, int, int, int]] = {}
    for key, node in nodes.items():
        _, _, height = measure_box(draw, node["desc"], node["writes"], width)
        rects[key] = (node["x"], node["y"], node["x"] + width, node["y"] + height)

    def center_bottom(key: str) -> tuple[int, int]:
        x0, y0, x1, y1 = rects[key]
        return (x0 + x1) // 2, y1

    def center_top(key: str) -> tuple[int, int]:
        x0, y0, x1, _ = rects[key]
        return (x0 + x1) // 2, y0

    def mid_y(key: str) -> int:
        _, y0, _, y1 = rects[key]
        return (y0 + y1) // 2

    # ---- 分区标题 ----
    draw.text((60 * SCALE, 108 * SCALE), "决策层", font=font(14, bold=True), fill=LANE_DECIDE)
    draw.text((60 * SCALE, 368 * SCALE), "纠错环 Corrective RAG", font=font(14, bold=True), fill=LANE_LOOP)
    draw.text((1110 * SCALE, 368 * SCALE), "并行层", font=font(14, bold=True), fill=LANE_PARALLEL)

    # ---- 连线 ----
    arrow(
        draw,
        [(290, rects["n1"][3]), (290, rects["n4"][1])],
        "simple",
        (302, rects["n1"][3] + 12),
    )
    arrow(draw, [(rects["n1"][2], 160), (rects["n2"][0], 160)], "complex", (455, 132))
    arrow(draw, [center_bottom("n2"), (center_bottom("n2")[0], rects["n3"][1])])
    arrow(
        draw,
        [(rects["n2"][2], 160), (1260, 160), (1260, rects["n8"][1])],
        "fan-out 并行",
        (950, 132),
    )
    arrow(draw, [(rects["n3"][2], mid_y("n3")), (1030, mid_y("n3"))])
    draw_end(draw, (1030, mid_y("n3") - 16, 1110, mid_y("n3") + 16))

    arrow(draw, [center_bottom("n4"), (center_bottom("n4")[0], rects["n5"][1])])
    arrow(
        draw,
        [(rects["n5"][2], mid_y("n5")), (500, mid_y("n5"))],
        "answer / clarify / no_knowledge",
        (455, mid_y("n5") - 34),
    )
    draw_end(draw, (500, mid_y("n5") - 16, 580, mid_y("n5") + 16))
    arrow(
        draw,
        [center_bottom("n5"), (center_bottom("n5")[0], rects["n6"][1])],
        "rewrite",
        (302, rects["n5"][3] + 12),
    )
    arrow(draw, [center_bottom("n6"), (center_bottom("n6")[0], rects["n7"][1])])
    arrow(
        draw,
        [
            (rects["n7"][0], mid_y("n7")),
            (90, mid_y("n7")),
            (90, mid_y("n5")),
            (rects["n5"][0], mid_y("n5")),
        ],
        "重评一次",
        (24, mid_y("n5") + 60),
        dashed=True,
    )

    arrow(
        draw,
        [center_bottom("n8"), (center_bottom("n8")[0], rects["n9"][1])],
        "x N 子问题",
        (1275, rects["n8"][3] + 12),
    )
    arrow(draw, [center_bottom("n9"), (center_bottom("n9")[0], rects["n9"][3] + 60)])
    draw_end(
        draw,
        (
            center_bottom("n9")[0] - 40,
            rects["n9"][3] + 60,
            center_bottom("n9")[0] + 40,
            rects["n9"][3] + 92,
        ),
    )

    # ---- 节点 ----
    for key, node in nodes.items():
        draw_box(
            draw,
            rects[key],
            node["index"],
            node["title"],
            node["desc"],
            node["writes"],
            node["color"],
        )

    # ---- 底部说明 ----
    legend = (
        "State 全集：question / query / docs / context / route / retrieval_status / "
        "evidence_* / missing_slots / hitl_* / rewrite_count / expansion_type / "
        "expanded_query / sub_questions / sub_results / rag_trace / request_context"
    )
    draw.text((40 * SCALE, (H - 56) * SCALE), legend, font=font(12), fill=MUTED)
    draw.text(
        (40 * SCALE, (H - 30) * SCALE),
        "简单题走左列 4→5 直接作答；复杂题经 2 分发到 8（每个子问题跑一遍 4→5→6→7），"
        "9 汇总后输出上下文；3 用于开放式多方向题的 HITL 追问。",
        font=font(12),
        fill=MUTED,
    )

    out = Path(__file__).resolve().parents[1] / "assets" / "rag-graph.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    print(f"已生成：{out}")


if __name__ == "__main__":
    main()
