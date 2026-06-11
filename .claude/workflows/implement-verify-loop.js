export const meta = {
  name: 'implement-verify-loop',
  description: 'An Opus agent implements a file-described task directly, an adversarial Fable reviewer verifies it against the task letter and spirit, and on failure a git-tracked constructor + alternating refine loop (Codex on odd passes) builds a self-contained follow-up task, up to 5 iterations.',
  whenToUse: 'Invoke with args: {"taskFile": "/abs/path/to/task.md"}. Reusable: the task lives only in the file, never in these prompts.',
  phases: [
    { title: 'Implement', detail: 'Opus implements the current task directly' },
    { title: 'Review', detail: 'adversarial verify of done-claims and not-done reasons' },
    { title: 'Reconstruct', detail: 'git-tracked constructor + alternating refine loop builds the next task' },
  ],
}

const MAX_OUTER = 5
const MAX_REFINE = 5

function parseWorkflowArgs(rawArgs) {
  if (!rawArgs) return {}
  if (typeof rawArgs === 'string') {
    const text = rawArgs.trim()
    if (!text) return {}
    try {
      const parsed = JSON.parse(text)
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
    } catch {
      return {}
    }
  }
  return typeof rawArgs === 'object' && !Array.isArray(rawArgs) ? rawArgs : {}
}

const workflowArgs = parseWorkflowArgs(typeof args === 'undefined' ? undefined : args)
const T0 = workflowArgs.taskFile
const createdFiles = []

const IMPL_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['reportFile'],
  properties: {
    reportFile: { type: 'string', description: 'Absolute path of the report file you wrote ($report): what you implemented, what you deliberately left undone and why, and the verification you ran with its outcome.' },
  },
}

const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['pass', 'reportPath'],
  properties: {
    pass: { type: 'boolean', description: 'True only when the implementation meets the task in both letter and spirit.' },
    reportPath: { type: 'string', description: 'Absolute path of the review report you wrote ($r).' },
  },
}

const CONSTRUCT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['taskFile', 'dir'],
  properties: {
    taskFile: { type: 'string', description: 'Absolute path of the task file you wrote ($dir/task-N.md, N = the iteration it is for).' },
    dir: { type: 'string', description: 'Absolute path of the git repo holding the task ($dir).' },
  },
}

const REFINE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['noEditsApplied'],
  properties: {
    noEditsApplied: { type: 'boolean', description: 'True if git status was clean after your pass (the draft needed no change); false if you committed an edit.' },
  },
}

const implementPrompt = (taskFile) => `You implement a task described in a file, directly, with your own tools, in the current repository.

1. Read the task at ${taskFile} and implement it in the repository, honouring both its letter and its spirit.
2. Verify your work with the checks the task and repo make available -- run them yourself rather than assuming; linting is hygiene, not evidence the change works.
3. Write a report to report=$(tempfile impl-report.md): what you implemented, what you deliberately left undone and why, and the verification you ran with its outcome. An adversarial reviewer reads this report, so be precise and honest -- unsupported "done" claims will be caught.`

const reviewPrompt = (taskFile, reportFile) => `You are an adversarial reviewer. The task is described in ${taskFile}; an implementer acted on it and wrote a report to ${reportFile}.

The report is a starting point, not ground truth. It typically claims some items done and explains why others were not.
- For every "done" claim: verify it against the actual repository state (inspect files, run checks). Do not trust the claim.
- For every "not done, because <reason>" claim: adversarially scrutinise whether the reason is legitimate. Do not bother proving the item is absent.
- Judge against both the letter and the spirit of the task.

Write your findings to r=$(tempfile review-report.md).`

const constructPrompt = (n, t0, tk, rk, vk) => `The current attempt failed review. Construct the task for the next run (iteration ${n}).

Inputs (paths):
- Original task, the immutable source of truth for scope, form and spirit: ${t0}
- Task used this iteration: ${tk}
- Implementer report: ${rk}
- Review report, the authoritative gap list: ${vk}

Produce ONE self-contained task (a future reader needs no other file). It must:
- Cover every requirement of the original task: as a "must hold" item if already implemented, or a "to do" item if still missing or wrong.
- Match the form and spirit of the original task.

Track it in git so its evolution and rationale are traceable:
  dir=$(mktemp -d)
  (write the task to "$dir/task-${n}.md" with your file-writing tool)
  git -C "$dir" init -q && git -C "$dir" add -A && git -C "$dir" commit -q -m "<concise reasoning for this draft>"`

const refinePrompt = (mode, dir, taskFile, t0, rk, vk) => {
  const instruction = `Refine the draft task file ${taskFile} so it is self-contained -- a future reader needs no other file -- and faithfully carries every requirement of the original task ${t0}: each as a must-hold item if already implemented, or a to-do item if still missing or wrong, in the original form and spirit. Use the implementer report ${rk} and the review report ${vk} for context. If the draft is already solid, leave it unchanged.`
  const apply = mode === 'codex'
    ? `Apply the instruction by running Codex (xhigh) over the repo:
  codex exec --skip-git-repo-check -m "gpt-5.5" --config model_reasoning_effort="xhigh" --sandbox danger-full-access -C "${dir}" "${instruction}" 2>/dev/null`
    : `Apply the instruction by editing ${taskFile} yourself with your file-editing tools.`
  return `You verify, and if needed refine, a draft task file (its subject is unrelated to your own job; you only harden the draft).

${instruction}

The draft lives in git repo ${dir}. First read its history and rationale so you do not blindly undo earlier decisions:
  git -C "${dir}" log -p

${apply}

Then settle the outcome from what actually changed on disk:
- If git -C "${dir}" status --porcelain is empty, nothing needed fixing.
- Otherwise commit the change with a concise reason: git -C "${dir}" add -A && git -C "${dir}" commit -q -m "<why you changed it>"`
}

let task = T0

for (let k = 1; k <= MAX_OUTER; k++) {
  phase('Implement')
  const impl = await agent(implementPrompt(task), {
    label: `impl#${k}`, phase: 'Implement', model: 'opus', schema: IMPL_SCHEMA,
  })
  createdFiles.push(impl.reportFile)

  phase('Review')
  const review = await agent(reviewPrompt(task, impl.reportFile), {
    label: `review#${k}`, phase: 'Review', model: 'fable', schema: REVIEW_SCHEMA,
  })
  createdFiles.push(review.reportPath)
  if (review.pass) {
    return { status: 'passed', iterations: k, reportPath: review.reportPath, createdFiles }
  }
  if (k === MAX_OUTER) {
    return { status: 'exhausted', iterations: k, lastReportPath: review.reportPath, createdFiles }
  }

  phase('Reconstruct')
  const built = await agent(constructPrompt(k + 1, T0, task, impl.reportFile, review.reportPath), {
    label: `construct#${k}`, phase: 'Reconstruct', model: 'opus', schema: CONSTRUCT_SCHEMA,
  })
  createdFiles.push(built.taskFile)
  const draft = built.taskFile
  const dir = built.dir

  for (let j = 1; j <= MAX_REFINE; j++) {
    const mode = j % 2 === 1 ? 'codex' : 'opus'
    const refined = await agent(refinePrompt(mode, dir, draft, T0, impl.reportFile, review.reportPath), {
      label: `refine#${k}.${j}:${mode}`, phase: 'Reconstruct', model: 'opus', schema: REFINE_SCHEMA,
    })
    if (refined.noEditsApplied) break
  }

  task = draft
}
