# 择命行效-行之有效的五行商业诊断理论体系·可视化模板库

本文件提供诊断报告中必备可视化内容的 SVG 模板代码。AI 在生成报告时，根据用户品牌的实际数据替换模板中的占位符（以 `{{}}` 标记），生成动态 SVG 图表。

> **版权声明**：本体系文字内容著作权归常亮所有，授权北京常识宋道商业咨询策划有限公司运营。

## 配色规范

```
之金：#D4A017（金色）
行水：#2196F3（蓝色）
有木：#4CAF50（绿色）
效火：#F44336（红色）
归土：#795548（棕色）
背景：#FFFFFF（浅色主题）/ #1E1E1E（深色主题）
文字：#333333（浅色主题）/ #E0E0E0（深色主题）
预警线：#FF9800（橙色）
断链标记：#F44336（红色）
正常标记：#4CAF50（绿色）
```

## 1. 五行链条诊断图（SVG 模板）

环形布局，五环依次排列，每环标注状态（生/泄/耗）。

```svg
<svg viewBox="0 0 680 400" xmlns="http://www.w3.org/2000/svg">
  <!-- 标题 -->
  <text x="340" y="30" text-anchor="middle" font-size="16" font-weight="bold" fill="#333">
    北京常识宋道·择命行效-行之有效的五行商业诊断理论体系·五行链条诊断图
  </text>
  <text x="340" y="50" text-anchor="middle" font-size="13" fill="#666">
    {{品牌名称}} · 诊断日期 {{诊断日期}}
  </text>

  <!-- 五行环形布局：金(上)→水(右上)→木(右下)→火(下)→土(左)→金(循环) -->
  <!-- 之金 -->
  <circle cx="340" cy="130" r="55" fill="none" stroke="{{金_边框色}}" stroke-width="{{金_线宽}}" stroke-dasharray="{{金_虚线}}"/>
  <text x="340" y="120" text-anchor="middle" font-size="14" font-weight="bold" fill="#D4A017">之金·下刀</text>
  <text x="340" y="140" text-anchor="middle" font-size="11" fill="{{金_状态色}}">{{金_状态}}</text>
  <text x="340" y="155" text-anchor="middle" font-size="10" fill="#666">{{金_表现}}</text>

  <!-- 行水 -->
  <circle cx="500" cy="200" r="55" fill="none" stroke="{{水_边框色}}" stroke-width="{{水_线宽}}" stroke-dasharray="{{水_虚线}}"/>
  <text x="500" y="190" text-anchor="middle" font-size="14" font-weight="bold" fill="#2196F3">行水·引水</text>
  <text x="500" y="210" text-anchor="middle" font-size="11" fill="{{水_状态色}}">{{水_状态}}</text>
  <text x="500" y="225" text-anchor="middle" font-size="10" fill="#666">{{水_表现}}</text>

  <!-- 有木 -->
  <circle cx="440" cy="330" r="55" fill="none" stroke="{{木_边框色}}" stroke-width="{{木_线宽}}" stroke-dasharray="{{木_虚线}}"/>
  <text x="440" y="320" text-anchor="middle" font-size="14" font-weight="bold" fill="#4CAF50">有木·植树</text>
  <text x="440" y="340" text-anchor="middle" font-size="11" fill="{{木_状态色}}">{{木_状态}}</text>
  <text x="440" y="355" text-anchor="middle" font-size="10" fill="#666">{{木_表现}}</text>

  <!-- 效火 -->
  <circle cx="240" cy="330" r="55" fill="none" stroke="{{火_边框色}}" stroke-width="{{火_线宽}}" stroke-dasharray="{{火_虚线}}"/>
  <text x="240" y="320" text-anchor="middle" font-size="14" font-weight="bold" fill="#F44336">效火·点火</text>
  <text x="240" y="340" text-anchor="middle" font-size="11" fill="{{火_状态色}}">{{火_状态}}</text>
  <text x="240" y="355" text-anchor="middle" font-size="10" fill="#666">{{火_表现}}</text>

  <!-- 归土 -->
  <circle cx="180" cy="200" r="55" fill="none" stroke="{{土_边框色}}" stroke-width="{{土_线宽}}" stroke-dasharray="{{土_虚线}}"/>
  <text x="180" y="190" text-anchor="middle" font-size="14" font-weight="bold" fill="#795548">归土·归藏</text>
  <text x="180" y="210" text-anchor="middle" font-size="11" fill="{{土_状态色}}">{{土_状态}}</text>
  <text x="180" y="225" text-anchor="middle" font-size="10" fill="#666">{{土_表现}}</text>

  <!-- 箭头连接：金→水→木→火→土→金(循环) -->
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="#999"/>
    </marker>
  </defs>
  <path d="M 380,150 Q 440,160 460,180" fill="none" stroke="#999" stroke-width="1.5" marker-end="url(#arrow)"/>
  <path d="M 500,255 Q 500,290 470,305" fill="none" stroke="#999" stroke-width="1.5" marker-end="url(#arrow)"/>
  <path d="M 385,330 Q 340,340 295,330" fill="none" stroke="#999" stroke-width="1.5" marker-end="url(#arrow)"/>
  <path d="M 210,305 Q 190,280 190,255" fill="none" stroke="#999" stroke-width="1.5" marker-end="url(#arrow)"/>
  <path d="M 220,170 Q 270,140 300,130" fill="none" stroke="#999" stroke-width="1.5" marker-end="url(#arrow)"/>

  <!-- 断链标记 -->
  {{断链标记SVG}}

  <!-- 底部标注 -->
  <text x="340" y="385" text-anchor="middle" font-size="11" fill="#999">
    行在知前 · 循环不息 · 效必归土
  </text>
</svg>
```

### 占位符替换规则

| 占位符 | 说明 | 取值规则 |
|--------|------|---------|
| `{{品牌名称}}` | 品牌名 | 用户输入的品牌名 |
| `{{金_状态}}` | 金环状态 | 生 / 泄 / 耗 |
| `{{金_表现}}` | 金环具体表现 | 10字以内摘要 |
| `{{金_边框色}}` | 边框颜色 | 生=#D4A017, 泄=#FF9800, 耗=#F44336 |
| `{{金_线宽}}` | 线宽 | 生=3, 泄=2, 耗=3 |
| `{{金_虚线}}` | 虚线样式 | 生=none, 泄=5,3, 耗=none |
| `{{金_状态色}}` | 状态文字色 | 生=#4CAF50, 泄=#FF9800, 耗=#F44336 |
| `{{断链标记SVG}}` | 断链处红色叉号 | 在断链环位置添加 `<text>✕</text>` |

（水/木/火/土 同理）

## 2. 四象定位图（SVG 模板）

坐标系：X轴=引水能力（水），Y轴=点火能力（火）。

```svg
<svg viewBox="0 0 680 450" xmlns="http://www.w3.org/2000/svg">
  <text x="340" y="25" text-anchor="middle" font-size="16" font-weight="bold" fill="#333">
    北京常识宋道·择命行效-行之有效的五行商业诊断理论体系·四象定位图
  </text>

  <!-- 坐标轴 -->
  <line x1="340" y1="50" x2="340" y2="400" stroke="#ccc" stroke-width="1"/>
  <line x1="80" y1="225" x2="600" y2="225" stroke="#ccc" stroke-width="1"/>

  <!-- 轴标签 -->
  <text x="610" y="230" font-size="12" fill="#666">引水能力（水）→</text>
  <text x="345" y="45" font-size="12" fill="#666">↑ 点火能力（火）</text>

  <!-- 四象分区填色 -->
  <!-- 老阳：右上（火旺水滥） -->
  <rect x="340" y="50" width="260" height="175" fill="#F44336" fill-opacity="0.08"/>
  <text x="470" y="80" text-anchor="middle" font-size="13" fill="#F44336" font-weight="bold">老阳</text>
  <text x="470" y="98" text-anchor="middle" font-size="10" fill="#F44336">火旺水滥</text>

  <!-- 少阳：右下（火生水蓄） -->
  <rect x="340" y="225" width="260" height="175" fill="#4CAF50" fill-opacity="0.08"/>
  <text x="470" y="255" text-anchor="middle" font-size="13" fill="#4CAF50" font-weight="bold">少阳</text>
  <text x="470" y="273" text-anchor="middle" font-size="10" fill="#4CAF50">火生水蓄</text>

  <!-- 少阴：左上（火弱水滞） -->
  <rect x="80" y="50" width="260" height="175" fill="#2196F3" fill-opacity="0.08"/>
  <text x="210" y="80" text-anchor="middle" font-size="13" fill="#2196F3" font-weight="bold">少阴</text>
  <text x="210" y="98" text-anchor="middle" font-size="10" fill="#2196F3">火弱水滞</text>

  <!-- 老阴：左下（火水俱衰） -->
  <rect x="80" y="225" width="260" height="175" fill="#9E9E9E" fill-opacity="0.08"/>
  <text x="210" y="255" text-anchor="middle" font-size="13" fill="#9E9E9E" font-weight="bold">老阴</text>
  <text x="210" y="273" text-anchor="middle" font-size="10" fill="#9E9E9E">火水俱衰</text>

  <!-- 品牌定位点（根据象位填入坐标） -->
  <circle cx="{{品牌X}}" cy="{{品牌Y}}" r="10" fill="{{品牌象色}}" stroke="#333" stroke-width="2"/>
  <text x="{{品牌X}}" y="{{品牌Y}}-18" text-anchor="middle" font-size="11" font-weight="bold" fill="#333">{{品牌名称}}</text>

  <!-- 对照案例点 -->
  <circle cx="{{对照1X}}" cy="{{对照1Y}}" r="6" fill="none" stroke="#999" stroke-width="1.5"/>
  <text x="{{对照1X}}" y="{{对照1Y}}-12" text-anchor="middle" font-size="10" fill="#999">{{对照1名称}}</text>

  <circle cx="{{对照2X}}" cy="{{对照2Y}}" r="6" fill="none" stroke="#999" stroke-width="1.5"/>
  <text x="{{对照2X}}" y="{{对照2Y}}-12" text-anchor="middle" font-size="10" fill="#999">{{对照2名称}}</text>

  <circle cx="{{对照3X}}" cy="{{对照3Y}}" r="6" fill="none" stroke="#999" stroke-width="1.5"/>
  <text x="{{对照3X}}" y="{{对照3Y}}-12" text-anchor="middle" font-size="10" fill="#999">{{对照3名称}}</text>

  <!-- 底部说明 -->
  <text x="340" y="430" text-anchor="middle" font-size="10" fill="#999">
    定位依据：水=停投后自然流占比，火=爆发后留存沉淀率
  </text>
</svg>
```

### 四象坐标映射规则

| 象位 | X范围 | Y范围 | 品牌象色 |
|------|-------|-------|---------|
| 老阳 | 380-580 | 60-200 | #F44336 |
| 少阳 | 380-580 | 250-390 | #4CAF50 |
| 少阴 | 100-300 | 60-200 | #2196F3 |
| 老阴 | 100-300 | 250-390 | #9E9E9E |

## 3. 治未病预警雷达图（SVG 模板）

五维雷达：金/水/木/火/土，标注各维读数与预警阈值。

```svg
<svg viewBox="0 0 680 450" xmlns="http://www.w3.org/2000/svg">
  <text x="340" y="25" text-anchor="middle" font-size="16" font-weight="bold" fill="#333">
    北京常识宋道·择命行效-行之有效的五行商业诊断理论体系·治未病预警雷达图
  </text>
  <text x="340" y="45" text-anchor="middle" font-size="12" fill="#666">{{品牌名称}} · 五诊读数</text>

  <!-- 雷达图中心 -->
  <!-- 五个方向：金(上) 水(右上72°) 木(右下72°) 火(左下72°) 土(左上72°) -->
  <!-- 半径=150, 中心=(340,225) -->

  <!-- 同心圆（4层，每层代表25%） -->
  <circle cx="340" cy="225" r="37.5" fill="none" stroke="#eee" stroke-width="1"/>
  <circle cx="340" cy="225" r="75" fill="none" stroke="#eee" stroke-width="1"/>
  <circle cx="340" cy="225" r="112.5" fill="none" stroke="#eee" stroke-width="1"/>
  <circle cx="340" cy="225" r="150" fill="none" stroke="#ddd" stroke-width="1.5"/>

  <!-- 预警阈值线（橙色虚线，位于60%处） -->
  <circle cx="340" cy="225" r="90" fill="none" stroke="#FF9800" stroke-width="1.5" stroke-dasharray="4,3"/>
  <text x="340" y="140" text-anchor="middle" font-size="9" fill="#FF9800">预警线（60%）</text>

  <!-- 五轴线 -->
  <line x1="340" y1="225" x2="340" y2="75" stroke="#ccc" stroke-width="1"/>   <!-- 金:上 -->
  <line x1="340" y1="225" x2="482" y2="178" stroke="#ccc" stroke-width="1"/>  <!-- 水:右上 -->
  <line x1="340" y1="225" x2="428" y2="367" stroke="#ccc" stroke-width="1"/>  <!-- 木:右下 -->
  <line x1="340" y1="225" x2="252" y2="367" stroke="#ccc" stroke-width="1"/>  <!-- 火:左下 -->
  <line x1="340" y1="225" x2="198" y2="178" stroke="#ccc" stroke-width="1"/>  <!-- 土:左上 -->

  <!-- 轴标签 -->
  <text x="340" y="65" text-anchor="middle" font-size="12" font-weight="bold" fill="#D4A017">之金</text>
  <text x="495" y="175" text-anchor="middle" font-size="12" font-weight="bold" fill="#2196F3">行水</text>
  <text x="438" y="385" text-anchor="middle" font-size="12" font-weight="bold" fill="#4CAF50">有木</text>
  <text x="242" y="385" text-anchor="middle" font-size="12" font-weight="bold" fill="#F44336">效火</text>
  <text x="185" y="175" text-anchor="middle" font-size="12" font-weight="bold" fill="#795548">归土</text>

  <!-- 读数数值标签 -->
  <text x="340" y="85" text-anchor="middle" font-size="10" fill="{{金_读数色}}">{{金_读数}}%</text>
  <text x="475" y="188" text-anchor="middle" font-size="10" fill="{{水_读数色}}">{{水_读数}}%</text>
  <text x="418" y="355" text-anchor="middle" font-size="10" fill="{{木_读数色}}">{{木_读数}}%</text>
  <text x="265" y="355" text-anchor="middle" font-size="10" fill="{{火_读数色}}">{{火_读数}}%</text>
  <text x="210" y="188" text-anchor="middle" font-size="10" fill="{{土_读数色}}">{{土_读数}}%</text>

  <!-- 数据多边形（根据读数计算顶点坐标） -->
  <polygon points="{{金_顶点X}},{{金_顶点Y}} {{水_顶点X}},{{水_顶点Y}} {{木_顶点X}},{{木_顶点Y}} {{火_顶点X}},{{火_顶点Y}} {{土_顶点X}},{{土_顶点Y}}"
           fill="{{多边形填充色}}" fill-opacity="0.2" stroke="{{多边形描边色}}" stroke-width="2"/>

  <!-- 底部说明 -->
  <text x="340" y="425" text-anchor="middle" font-size="10" fill="#999">
    读数低于60%触发预警 | 金=定位清晰度 水停投留存 木=壁垒深度 火=爆发沉淀 土=复购占比
  </text>
</svg>
```

### 雷达图顶点计算规则

中心点 `(340, 225)`，最大半径 `150`。读数 `score`（0-100）对应的顶点坐标：

| 维度 | 角度 | X = 340 + r·cos(θ) | Y = 225 - r·sin(θ) | r = 150 · score/100 |
|------|------|---------------------|---------------------|---------------------|
| 金 | 90° | 340 | 225 - r | 上方 |
| 水 | 18° | 340 + r·0.951 | 225 - r·0.309 | 右上 |
| 木 | -54° | 340 + r·0.588 | 225 + r·0.809 | 右下 |
| 火 | -126° | 340 - r·0.588 | 225 + r·0.809 | 左下 |
| 土 | 162° | 340 - r·0.951 | 225 - r·0.309 | 左上 |

## 4. 断链与修复序列表（HTML 模板）

> **格式要求**：输出时必须使用 HTML `<table>`，禁止退化为 Markdown 表格。以下为内容骨架，生成报告时转为 HTML `<table>` 嵌入报告。

```html
<table>
  <thead>
    <tr><th>五行环</th><th>当前状态</th><th>断链判定</th><th>具体表现</th><th>修复优先级</th><th>预计周期</th></tr>
  </thead>
  <tbody>
    <tr><td>之金·下刀</td><td>{{金_状态}}</td><td>{{金_是否断链}}</td><td>{{金_表现描述}}</td><td>{{金_优先级}}</td><td>{{金_周期}}</td></tr>
    <tr><td>行水·引水</td><td>{{水_状态}}</td><td>{{水_是否断链}}</td><td>{{水_表现描述}}</td><td>{{水_优先级}}</td><td>{{水_周期}}</td></tr>
    <tr><td>有木·植树</td><td>{{木_状态}}</td><td>{{木_是否断链}}</td><td>{{木_表现描述}}</td><td>{{木_优先级}}</td><td>{{木_周期}}</td></tr>
    <tr><td>效火·点火</td><td>{{火_状态}}</td><td>{{火_是否断链}}</td><td>{{火_表现描述}}</td><td>{{火_优先级}}</td><td>{{火_周期}}</td></tr>
    <tr><td>归土·归藏</td><td>{{土_状态}}</td><td>{{土_是否断链}}</td><td>{{土_表现描述}}</td><td>{{土_优先级}}</td><td>{{土_周期}}</td></tr>
  </tbody>
</table>

**主断链点**：{{主断链环}}
**修复顺序**：{{修复顺序}}（从主断点起顺行，详见 SKILL.md 处方铁律）
**验收标准**：90天后复检土指标三件套——复购率 ≥ {{复购目标}}%、自然流占比 ≥ {{自然流目标}}%、老客成交占比 ≥ {{老客目标}}%
```

## 5. 度·因果秤杆图（SVG 模板）

展示"度"在因果之间的偏移。

```svg
<svg viewBox="0 0 680 300" xmlns="http://www.w3.org/2000/svg">
  <text x="340" y="25" text-anchor="middle" font-size="16" font-weight="bold" fill="#333">
    北京常识宋道·择命行效-行之有效的五行商业诊断理论体系·度·因果秤杆图
  </text>

  <!-- 因果两极 -->
  <text x="120" y="80" text-anchor="middle" font-size="15" font-weight="bold" fill="#2196F3">因（行）</text>
  <text x="560" y="80" text-anchor="middle" font-size="15" font-weight="bold" fill="#F44336">果（效）</text>

  <!-- 秤杆 -->
  <line x1="120" y1="100" x2="560" y2="100" stroke="#999" stroke-width="3"/>

  <!-- 秤杆刻度 -->
  <line x1="120" y1="95" x2="120" y2="105" stroke="#666" stroke-width="1"/>
  <line x1="230" y1="95" x2="230" y2="105" stroke="#ccc" stroke-width="1"/>
  <line x1="340" y1="90" x2="340" y2="110" stroke="#666" stroke-width="2"/>
  <line x1="450" y1="95" x2="450" y2="105" stroke="#ccc" stroke-width="1"/>
  <line x1="560" y1="95" x2="560" y2="105" stroke="#666" stroke-width="1"/>

  <text x="340" y="125" text-anchor="middle" font-size="10" fill="#999">平衡点</text>

  <!-- 秤砣（位置根据度偏移方向计算） -->
  <circle cx="{{秤砣X}}" cy="100" r="18" fill="#D4A017" stroke="#B8860B" stroke-width="2"/>
  <text x="{{秤砣X}}" y="105" text-anchor="middle" font-size="12" font-weight="bold" fill="white">度</text>

  <!-- 偏移方向标注 -->
  <text x="{{秤砣X}}" y="75" text-anchor="middle" font-size="11" fill="{{偏移色}}">{{偏移方向}}</text>
  <text x="{{秤砣X}}" y="145" text-anchor="middle" font-size="10" fill="#666">{{偏移说明}}</text>

  <!-- 底部说明 -->
  <text x="340" y="180" text-anchor="middle" font-size="11" fill="#666">
    度是滑动在因果之间的秤砣——偏向因则行有余而效不足，偏向果则急效而忘行
  </text>
  <text x="340" y="200" text-anchor="middle" font-size="10" fill="#999">
    度的测量：四象地形仪器 + 治未病体检单预警线
  </text>

  <!-- 五行过与不及标记 -->
  <text x="120" y="240" text-anchor="middle" font-size="10" fill="#2196F3">行之过：{{行之过}}</text>
  <text x="560" y="240" text-anchor="middle" font-size="10" fill="#F44336">效之过：{{效之过}}</text>

  <text x="340" y="270" text-anchor="middle" font-size="11" fill="#999">
    行在知前 · 循环不息 · 效必归土
  </text>
</svg>
```

### 秤砣位置计算

| 偏移方向 | 秤砣X | 偏移色 | 说明 |
|---------|-------|-------|------|
| 偏向因（行有余效不足） | 120-280 | #2196F3 | 行动过度但效果未显 |
| 平衡 | 340 | #4CAF50 | 因果协调 |
| 偏向果（急效忘行） | 400-560 | #F44336 | 追求短期效果忽视行动根基 |

## 6. 配图引用规范

在报告 Markdown 中引用 assets/ 下的理论配图时，使用以下格式：

```markdown
### [章节名]

![配图说明](assets/XX_配图名.png)

*如上图所示，{{品牌名称}}的五行链条呈现{{具体描述}}。{{结合配图的分析文字}}。*
```

### 配图引用时机

| 报告章节 | 引用配图 | 用途 |
|---------|---------|------|
| 概述/理论框架 | 01_因果两极五行输运图 | 展示理论框架 |
| 五行链条诊断 | 02_五行行动链循环图 | 对照品牌链条 |
| 四象判定 | 05_四象地形状态图 | 展示象位 |
| 断链定位 | 09_五行过与不及图 | 展示过与不及 |
| 度分析 | 08_度_因果秤杆图 | 展示度偏移 |
| 鞍点论证 | 04_鞍点地形图.png | 展示地形位置 |
| 案例对照 | 12_苹果五行链图_出版版 | 对照标准案例 |
| 行业分析 | 11_行业五行定位图 | 行业五行特征 |
| 诊断流程 | 06_五诊五问流程图 | 展示诊断过程 |
| 三才定位 | 07_三才定位结构图 | 展示三才结构 |
| SWOT对照 | 10_SWOT对比五行图 | SWOT-五行对照 |
| 五行关系 | 03_五行相生相克双环图 | 相生相克分析 |

## 7. 动态数据填充示例

以下是一个完整的五行链条诊断图数据填充示例：

**用户品牌**：某咖啡品牌
**诊断结果**：金生、水泄、木耗、火泄、土耗

**填充后的 SVG 参数**：

```
品牌名称 = 某咖啡品牌
金_状态 = 生    金_边框色 = #D4A017  金_线宽 = 3   金_虚线 = none    金_状态色 = #4CAF50
金_表现 = 定位清晰

水_状态 = 泄    水_边框色 = #FF9800  水_线宽 = 2   水_虚线 = 5,3    水_状态色 = #FF9800
水_表现 = 泵抽式引水

木_状态 = 耗    木_边框色 = #F44336  木_线宽 = 3   木_虚线 = none    木_状态色 = #F44336
木_表现 = 全代工无壁垒

火_状态 = 泄    火_边框色 = #FF9800  火_线宽 = 2   火_虚线 = 5,3    火_状态色 = #FF9800
火_表现 = 爆发不沉淀

土_状态 = 耗    土_边框色 = #F44336  土_线宽 = 3   土_虚线 = none    土_状态色 = #F44336
土_表现 = 无复购资产

断链标记SVG = 在木和土位置添加红色✕
```

## 8. 注意事项

1. **SVG 尺寸**：所有 SVG 使用 `viewBox="0 0 680 XXX"`，宽度固定 680，高度根据内容调整
2. **字体**：使用系统默认字体，不指定特殊字体
3. **深色主题适配**：当用户 IDE 为深色主题时，将 `fill="#333"` 改为 `fill="#E0E0E0"`，背景改为深色
4. **数据隐私**：图表中不显示用户的敏感财务数据原始值，用百分比或区间表示
5. **对照案例**：四象定位图中的对照案例从 240 案库中按象位匹配，最多显示 3 个
6. **配图缺失处理**：如 assets/ 目录下缺少某张配图，跳过引用，用 SVG 动态生成的图表替代
