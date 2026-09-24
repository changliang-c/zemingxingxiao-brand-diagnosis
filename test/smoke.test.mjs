import { test } from 'node:test'
import assert from 'node:assert/strict'
import { pathToFileURL } from 'node:url'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const PLUGIN_URL = pathToFileURL(join(dirname(fileURLToPath(import.meta.url)), '..', 'dsh', 'index.js')).href

function makeCtx() {
  const registered = []
  const sections = []
  const effects = []
  const ctx = {
    skills: {
      register(skill) {
        registered.push(skill)
        return () => {
          const i = registered.indexOf(skill)
          if (i >= 0) registered.splice(i, 1)
        }
      },
    },
    systemPrompt: {
      section(sec) {
        sections.push(sec)
        return () => {
          const i = sections.indexOf(sec)
          if (i >= 0) sections.splice(i, 1)
        }
      },
    },
    effect(fn, name) {
      const dispose = fn()
      effects.push({ name, dispose })
      return dispose
    },
  }
  return { ctx, registered, sections, effects }
}

test('plugin shape: name + inject declared', async () => {
  const mod = await import(PLUGIN_URL)
  assert.equal(mod.name, 'zemingxingxiao-brand-diagnosis')
  assert.deepEqual(mod.inject, ['skills', 'systemPrompt'])
  assert.equal(typeof mod.apply, 'function')
})

test('apply registers 1 main skill + 5 companion skills + 1 router section', async () => {
  const mod = await import(PLUGIN_URL)
  const { ctx, registered, sections } = makeCtx()

  mod.apply(ctx)

  assert.equal(registered.length, 6)
  const names = registered.map((s) => s.name)
  assert.deepEqual(names, [
    'zemingxingxiao-brand-diagnosis',
    'zemingxingxiao-theory',
    'zemingxingxiao-diagnosis',
    'zemingxingxiao-cases',
    'zemingxingxiao-visual-templates',
    'zemingxingxiao-glossary',
  ])
  for (const s of registered) {
    assert.equal(s.source, 'runtime')
    assert.ok(s.description.length > 10, `${s.name} needs a routing description`)
    assert.ok(s.content.length > 200, `${s.name} content looks empty`)
    assert.ok(!s.content.startsWith('---'), `${s.name} frontmatter should be stripped`)
  }

  assert.equal(sections.length, 1)
  assert.equal(sections[0].name, 'zemingxingxiao:router')
  assert.ok(sections[0].text.includes('zemingxingxiao-brand-diagnosis'))
})

test('main skill content resolves real on-disk asset paths', async () => {
  const mod = await import(PLUGIN_URL)
  const { ctx, registered } = makeCtx()
  mod.apply(ctx)

  const main = registered.find((s) => s.name === 'zemingxingxiao-brand-diagnosis')
  const { existsSync } = await import('node:fs')
  const tpl = main.content.match(/`((?:[A-Za-z]:)?[\\/][^`]*references\/report_template\.html)`/)
  assert.ok(tpl, 'absolute report template path missing from main skill content')
  assert.ok(existsSync(tpl[1]), `report template not found on disk: ${tpl[1]}`)
  const assets = main.content.match(/`((?:[A-Za-z]:)?[\\/][^`]*?[\\/]assets)\//)
  assert.ok(assets && existsSync(assets[1]), 'assets dir missing or not on disk')
})

test('dispose tears down every registration', async () => {
  const mod = await import(PLUGIN_URL)
  const { ctx, registered, sections, effects } = makeCtx()
  mod.apply(ctx)
  assert.equal(effects.length, 1)

  effects[0].dispose()
  assert.equal(registered.length, 0)
  assert.equal(sections.length, 0)
})
