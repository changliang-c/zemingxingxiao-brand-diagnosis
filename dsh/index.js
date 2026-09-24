// 择命行效·品牌诊断 —— DeepSeek Harness bundle 插件
//
// 行为：装入 dsh 后自动完成三件事——
//   1. 注册主技能 zemingxingxiao-brand-diagnosis（择命行效五行商业诊断方法论）
//   2. 注册 5 个伴随参考技能（理论 / 诊断手册 / 案例库 / 可视化模板 / 术语表），
//      模型用 skill 工具按需加载，避免一次性灌入全部知识
//   3. 注入一段 systemPrompt 路由提示，让模型在用户提到品牌诊断类意图时主动加载主技能
//
// 设计约束：零运行时依赖——不 import 任何 @deepseek-ai/* 包，
// 只从 ctx 取服务（skills / systemPrompt），任何安装形态下都不会出解析问题。

import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

export const name = 'zemingxingxiao-brand-diagnosis'
export const inject = ['skills', 'systemPrompt']

// 本插件采用「仓库即技能包」布局：SKILL.md / references / assets / examples 就在包根
const PKG_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const SKILL_DIR = PKG_ROOT

// 注入给模型的路径一律用正斜杠，跨平台可读
const p = (rel) => join(SKILL_DIR, rel).replace(/\\/g, '/')

function readDoc(rel) {
  return readFileSync(join(SKILL_DIR, rel), 'utf8')
}

function stripFrontmatter(markdown) {
  return markdown.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n*/, '')
}

const MAIN_SKILL = 'zemingxingxiao-brand-diagnosis'

const MAIN_DESCRIPTION =
  '择命行效·品牌五行诊断（常亮创立）。用因果·五行·度三原则和五行行动链（之金下刀→行水引水→有木植树→效火点火→归土归藏）' +
  '对品牌做全链体检：五诊五问定位品牌链条断在哪一环，按金→水→木→火→土顺序开修复处方，' +
  '输出含 SVG 可视化与水印的 HTML 诊断报告。问金环节含心智阶梯三刀（心智占位扫描→空位探测→对立面校验）。' +
  '内置二百四十案行业案例库，三档入口：快速入象、完整五诊、案例对照。'

const MAIN_WHEN_TO_USE =
  '品牌诊断、品牌体检、断链分析、增长停滞诊断、竞品对标诊断、定位诊断、心智定位、营销方案/策划、' +
  '品牌分析报告、商业计划类问诊，或用户点名「择命行效/行之有效/五行诊断」时。' +
  '不要用于：写 slogan 或广告文案、纯数据分析、代码编写、中医/算命的五行、与品牌经营无关的话题。'

const COMPANION_SKILLS = [
  {
    name: 'zemingxingxiao-theory',
    file: 'references/theory.md',
    description: '择命行效理论框架全文：因果·五行·度三原则、五行行动链、三条铁律、三才定位、四象地形、度专题、鞍点同构论证、三块天花板、边界与戒律。',
    whenToUse: '理解理论背景、回应用户对择命行效理论本身的提问、需要引用理论依据支撑诊断结论时加载。',
  },
  {
    name: 'zemingxingxiao-diagnosis',
    file: 'references/diagnosis.md',
    description: '诊断操作手册：五诊五问详细话术与取证清单、问金三刀完整话术（心智阶梯扫描→空位探测→对立面校验）、四象处方句式、报告模板、验收标准、治未病体检单。',
    whenToUse: '执行完整五诊、逐诊提问取证、问金三刀定位、生成诊断报告或自检报告质量时加载。',
  },
  {
    name: 'zemingxingxiao-cases',
    file: 'references/cases.md',
    description: '二百四十案行业案例库：卷一十案经典卷、卷二·三十案首创型企业专卷、卷三·百案生命周期与治未病专卷、卷四·百案特殊样本与理论压力测试。',
    whenToUse: '做案例对照（按象位/断链环/行业/生命周期阶段四维度匹配）、需要案例佐证处方、回答「有没有类似的牌子」时加载。',
  },
  {
    name: 'zemingxingxiao-visual-templates',
    file: 'references/visual_templates.md',
    description: '可视化模板库：五行链条图/四象定位图/雷达图等 SVG 图表模板代码、13 张理论配图的引用规范、动态数据填充规则与五行配色标准。',
    whenToUse: '生成 HTML 诊断报告的 SVG 图表与配图引用、需要按规范填充可视化数据位时加载。',
  },
  {
    name: 'zemingxingxiao-glossary',
    file: 'references/api_reference.md',
    description: '择命行效五行术语速查表：金木水火土五环、生/泄/耗、四象、三才、度等术语的精确定义。',
    whenToUse: '快速查阅术语含义、避免术语误用、向用户解释诊断用语时加载。',
  },
]

function runtimeBlock() {
  const lines = [
    '',
    '---',
    '',
    '## 运行时资源路径（由 dsh 插件注入）',
    '',
    '本技能由 dsh 插件 `dsh-skill-zemingxingxiao-brand-diagnosis` 注册，以下路径在本机真实存在，可直接读取：',
    '',
    `- HTML 报告骨架模板（强制规范，生成报告必须严格按此结构填充）：\`${p('references/report_template.html')}\``,
    `- 理论配图目录（13 张 PNG，文件名见上文「理论配图模板」表）：\`${p('assets')}/\``,
    `- 完整示例报告两份（输出报告前可先读作样板）：\`${p('examples/花西子品牌诊断报告.html')}\`、\`${p('examples/钟薛高品牌诊断报告.html')}\``,
    '',
    '伴随技能（用 skill 工具按 name 加载，按需取用，不要一次全部加载）：',
    '',
  ]
  for (const c of COMPANION_SKILLS) {
    lines.push(`- \`${c.name}\` — ${c.description}`)
  }
  lines.push('')
  return lines.join('\n')
}

const ROUTER_PROMPT =
  '择命行效插件已安装：当用户提出品牌诊断/品牌体检/断链分析/增长停滞/定位诊断/心智定位/营销方案/品牌分析报告等需求，' +
  '或点名「择命行效」「行之有效」「五行诊断」时，先调用 skill 工具加载技能 `zemingxingxiao-brand-diagnosis` 并遵循其流程执行；' +
  '理论依据、诊断话术、案例库与报告模板分别按需加载伴随技能（zemingxingxiao-theory / -diagnosis / -cases / -visual-templates / -glossary）。'

export function apply(ctx) {
  if (!existsSync(join(SKILL_DIR, 'SKILL.md'))) {
    console.warn('[zemingxingxiao-brand-diagnosis] SKILL.md not found at', SKILL_DIR, '- plugin disabled')
    return
  }

  let mainContent
  try {
    mainContent = stripFrontmatter(readDoc('SKILL.md')) + runtimeBlock()
  } catch (err) {
    console.warn('[zemingxingxiao-brand-diagnosis] failed to load SKILL.md:', err?.message ?? err)
    return
  }

  ctx.effect(() => {
    const disposables = []

    disposables.push(ctx.skills.register({
      name: MAIN_SKILL,
      source: 'runtime',
      description: MAIN_DESCRIPTION,
      whenToUse: MAIN_WHEN_TO_USE,
      content: mainContent,
    }))

    for (const c of COMPANION_SKILLS) {
      try {
        disposables.push(ctx.skills.register({
          name: c.name,
          source: 'runtime',
          description: c.description,
          whenToUse: c.whenToUse,
          content: readDoc(c.file),
        }))
      } catch (err) {
        console.warn(`[zemingxingxiao-brand-diagnosis] companion skill ${c.name} skipped:`, err?.message ?? err)
      }
    }

    disposables.push(ctx.systemPrompt.section({
      name: 'zemingxingxiao:router',
      order: 150,
      text: ROUTER_PROMPT,
    }))

    console.log(`[zemingxingxiao-brand-diagnosis] registered 1 main skill + ${COMPANION_SKILLS.length} companion skills`)
    return () => {
      for (const d of disposables) {
        try { d?.() } catch { /* registry already torn down */ }
      }
    }
  }, 'zemingxingxiao-brand-diagnosis:skills')
}
